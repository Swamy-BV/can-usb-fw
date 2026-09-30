/* Minimal host-side DFU 1.1 suffix writer for CANnectivity's CMake target. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int number(const char *text, uint16_t *out)
{
    char *end;
    unsigned long value = strtoul(text, &end, 0);
    if (text == end || *end != '\0' || value > 0xffffUL) {
        return -1;
    }
    *out = (uint16_t)value;
    return 0;
}

static uint32_t crc_byte(uint32_t crc, uint8_t byte)
{
    unsigned bit;
    crc ^= byte;
    for (bit = 0; bit < 8; ++bit) {
        crc = (crc >> 1) ^ ((crc & 1U) ? 0xedb88320U : 0U);
    }
    return crc;
}

int main(int argc, char **argv)
{
    uint16_t vid = 0xffffU, pid = 0xffffU, spec = 0x0110U;
    uint8_t tail[16];
    uint8_t chunk[4096];
    uint32_t crc = 0xffffffffU;
    size_t count;
    FILE *image;
    const char *path = NULL;
    int i;

    for (i = 1; i < argc; ++i) {
        if ((strcmp(argv[i], "--vid") == 0 || strcmp(argv[i], "--pid") == 0 ||
             strcmp(argv[i], "--spec") == 0) && i + 1 < argc) {
            uint16_t *destination = strcmp(argv[i], "--vid") == 0 ? &vid :
                                    strcmp(argv[i], "--pid") == 0 ? &pid : &spec;
            if (number(argv[++i], destination) != 0) {
                fprintf(stderr, "invalid DFU numeric option\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--add") == 0 && i + 1 < argc) {
            path = argv[++i];
        } else {
            fprintf(stderr, "usage: dfu_suffix --vid N --pid N --spec N --add IMAGE\n");
            return 2;
        }
    }
    if (path == NULL || (image = fopen(path, "rb+")) == NULL) {
        perror("opening DFU image");
        return 1;
    }
    while ((count = fread(chunk, 1, sizeof(chunk), image)) != 0U) {
        size_t j;
        for (j = 0; j < count; ++j) {
            crc = crc_byte(crc, chunk[j]);
        }
    }
    if (ferror(image) || fseek(image, 0, SEEK_END) != 0) {
        perror("reading DFU image");
        fclose(image);
        return 1;
    }
    tail[0] = 0xffU; tail[1] = 0xffU;
    tail[2] = (uint8_t)pid; tail[3] = (uint8_t)(pid >> 8);
    tail[4] = (uint8_t)vid; tail[5] = (uint8_t)(vid >> 8);
    tail[6] = (uint8_t)spec; tail[7] = (uint8_t)(spec >> 8);
    tail[8] = 'U'; tail[9] = 'F'; tail[10] = 'D'; tail[11] = 16U;
    for (i = 0; i < 12; ++i) {
        crc = crc_byte(crc, tail[i]);
    }
    tail[12] = (uint8_t)crc; tail[13] = (uint8_t)(crc >> 8);
    tail[14] = (uint8_t)(crc >> 16); tail[15] = (uint8_t)(crc >> 24);
    if (fwrite(tail, 1, sizeof(tail), image) != sizeof(tail) || fclose(image) != 0) {
        perror("writing DFU suffix");
        return 1;
    }
    return 0;
}
