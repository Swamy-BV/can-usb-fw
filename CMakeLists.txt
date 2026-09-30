cmake_minimum_required(VERSION 3.20)
project(can_usb_fw LANGUAGES C)

# West only fetches sources. This project builds the paired MCUboot and app
# images; Zephyr/MCUboot perform the actual image signing.
set(FW_TOOLCHAIN_ROOT "" CACHE PATH "Arm GNU toolchain root")
set(FW_SIGNING_KEY "" CACHE FILEPATH "One MCUboot ECDSA P-256 PEM key for both images")
set(FW_VERSION "1.2.0" CACHE STRING "Application image version")
set(FW_PYTHON_EXECUTABLE "" CACHE FILEPATH "Python with Zephyr build requirements")

if(NOT FW_TOOLCHAIN_ROOT OR NOT EXISTS "${FW_TOOLCHAIN_ROOT}/bin/arm-none-eabi-gcc${CMAKE_EXECUTABLE_SUFFIX}")
  message(FATAL_ERROR "Set FW_TOOLCHAIN_ROOT to the Arm GNU toolchain directory")
endif()
if(NOT FW_SIGNING_KEY OR NOT EXISTS "${FW_SIGNING_KEY}")
  message(FATAL_ERROR "Set FW_SIGNING_KEY to an existing ECDSA P-256 PEM file")
endif()
if(NOT FW_VERSION MATCHES "^[0-9]+\.[0-9]+\.[0-9]+$")
  message(FATAL_ERROR "FW_VERSION must be major.minor.patch")
endif()
if(NOT FW_PYTHON_EXECUTABLE)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  set(FW_PYTHON_EXECUTABLE "${Python3_EXECUTABLE}")
endif()

get_filename_component(FW_TOOLCHAIN_ROOT "${FW_TOOLCHAIN_ROOT}" ABSOLUTE)
get_filename_component(FW_SIGNING_KEY "${FW_SIGNING_KEY}" ABSOLUTE)
get_filename_component(FW_PYTHON_EXECUTABLE "${FW_PYTHON_EXECUTABLE}" ABSOLUTE)
file(TO_CMAKE_PATH "${FW_TOOLCHAIN_ROOT}" FW_TOOLCHAIN_ROOT)
file(TO_CMAKE_PATH "${FW_SIGNING_KEY}" FW_SIGNING_KEY)
file(TO_CMAKE_PATH "${FW_PYTHON_EXECUTABLE}" FW_PYTHON_EXECUTABLE)

set(deps "${CMAKE_SOURCE_DIR}/.deps")
set(zephyr "${deps}/zephyr/zephyr")
set(mcuboot "${deps}/zephyr/bootloader/mcuboot")
set(cannectivity "${deps}/cannectivity")
set(modules
  "${deps}/zephyr/modules/hal/cmsis"
  "${deps}/zephyr/modules/hal/cmsis_6"
  "${deps}/zephyr/modules/hal/nxp"
  "${mcuboot}"
  "${deps}/zephyr/modules/crypto/mbedtls"
  "${cannectivity}"
  "${CMAKE_SOURCE_DIR}/platform/mcxn236_control")
foreach(required "${zephyr}/CMakeLists.txt" "${mcuboot}/boot/zephyr/CMakeLists.txt"
                 "${cannectivity}/app/CMakeLists.txt")
  if(NOT EXISTS "${required}")
    message(FATAL_ERROR "Missing ${required}; run west update first")
  endif()
endforeach()

file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/generated")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  "${CMAKE_SOURCE_DIR}/board/mcuboot-bootloader.conf"
  "${CMAKE_SOURCE_DIR}/board/frdm_mcxn236.conf"
  "${CMAKE_SOURCE_DIR}/board/mcuboot.conf"
  "${CMAKE_SOURCE_DIR}/board/partitions.overlay"
  "${CMAKE_SOURCE_DIR}/board/two-channel.overlay")
function(write_if_changed path contents)
  if(EXISTS "${path}")
    file(READ "${path}" previous)
    if("${previous}" STREQUAL "${contents}")
      return()
    endif()
  endif()
  file(WRITE "${path}" "${contents}")
endfunction()
file(READ "${CMAKE_SOURCE_DIR}/board/mcuboot-bootloader.conf" boot_conf)
write_if_changed("${CMAKE_BINARY_DIR}/generated/boot.conf"
  "${boot_conf}\nCONFIG_BOOT_SIGNATURE_KEY_FILE=\"${FW_SIGNING_KEY}\"\n")
file(READ "${CMAKE_SOURCE_DIR}/board/frdm_mcxn236.conf" app_conf)
file(READ "${CMAKE_SOURCE_DIR}/board/mcuboot.conf" app_mcuboot_conf)
write_if_changed("${CMAKE_BINARY_DIR}/generated/app.conf"
  "${app_conf}\n${app_mcuboot_conf}\nCONFIG_MCUBOOT_SIGNATURE_KEY_FILE=\"${FW_SIGNING_KEY}\"\nCONFIG_MCUBOOT_IMGTOOL_SIGN_VERSION=\"${FW_VERSION}\"\n")
file(READ "${CMAKE_SOURCE_DIR}/board/partitions.overlay" partitions)
file(READ "${CMAKE_SOURCE_DIR}/board/two-channel.overlay" channels)
write_if_changed("${CMAKE_BINARY_DIR}/generated/boot.overlay" "${partitions}\n")
write_if_changed("${CMAKE_BINARY_DIR}/generated/app.overlay" "${partitions}\n${channels}\n")

add_executable(fw_dfu_suffix tools/dfu_suffix.c)

function(firmware_image name source conf overlay)
  set(out "${CMAKE_BINARY_DIR}/${name}")
  add_custom_command(OUTPUT "${out}/configured.stamp"
    COMMAND ${CMAKE_COMMAND} -E env
      "ZEPHYR_BASE=${zephyr}"
      "ZEPHYR_TOOLCHAIN_VARIANT=gnuarmemb"
      "GNUARMEMB_TOOLCHAIN_PATH=${FW_TOOLCHAIN_ROOT}"
      ${CMAKE_COMMAND} -S "${source}" -B "${out}" -G Ninja
      "-DBOARD=frdm_mcxn236"
      "-DZEPHYR_MODULES=${modules}"
      "-DEXTRA_CONF_FILE=${conf}"
      "-DEXTRA_DTC_OVERLAY_FILE=${overlay}"
      "-DPython3_EXECUTABLE=${FW_PYTHON_EXECUTABLE}"
      "-DCMAKE_MAKE_PROGRAM=${FW_NINJA}"
      "-DDFU_SUFFIX=$<TARGET_FILE:fw_dfu_suffix>"
    COMMAND ${CMAKE_COMMAND} -E touch "${out}/configured.stamp"
    DEPENDS "${conf}" "${overlay}" fw_dfu_suffix
    VERBATIM)
  add_custom_target(${name}_configure DEPENDS "${out}/configured.stamp")
  add_custom_target(${name} ALL
    COMMAND ${CMAKE_COMMAND} --build "${out}"
    DEPENDS ${name}_configure
    USES_TERMINAL VERBATIM)
endfunction()

find_program(FW_NINJA ninja REQUIRED)
firmware_image(bootloader "${mcuboot}/boot/zephyr"
  "${CMAKE_BINARY_DIR}/generated/boot.conf" "${CMAKE_BINARY_DIR}/generated/boot.overlay")
firmware_image(app "${cannectivity}/app"
  "${CMAKE_BINARY_DIR}/generated/app.conf" "${CMAKE_BINARY_DIR}/generated/app.overlay")
add_dependencies(app bootloader fw_dfu_suffix)

message(STATUS "Lab-only USB identity: 1FC9:00A2; app version: ${FW_VERSION}")
message(STATUS "One external signing key: ${FW_SIGNING_KEY}")
