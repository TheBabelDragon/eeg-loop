# ESP-IDF component-style CMake for the acquisition bridge.
# Build with ESP-IDF export.sh environment, or host-test the pure-C units.
#
# Host unit test (no ESP-IDF required):
#   cc -I include -o test_packet src/packet_encoder.c src/transport.c test/test_packet_encoder.c
#   ./test_packet

cmake_minimum_required(VERSION 3.16)

# When building as a standalone IDF project:
# include($ENV{IDF_PATH}/tools/cmake/project.cmake)
# project(eeg_acquisition_bridge)

# Pure-C library for host tests / shared logic
add_library(eeg_packet STATIC
    src/packet_encoder.c
    src/transport.c
)
target_include_directories(eeg_packet PUBLIC include)

# Optional host test executable
option(EEG_HOST_TESTS "Build host-side packet encoder tests" ON)
if(EEG_HOST_TESTS)
    add_executable(test_packet_encoder test/test_packet_encoder.c)
    target_link_libraries(test_packet_encoder eeg_packet)
    target_include_directories(test_packet_encoder PRIVATE include)
endif()
