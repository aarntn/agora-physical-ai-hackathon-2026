# Drop this folder into an ESP-IDF project's components/ directory,
# or build the host parity test with plain CMake.
if(ESP_PLATFORM)
  idf_component_register(SRCS "nasocheck_dsp.c" INCLUDE_DIRS ".")
else()
  cmake_minimum_required(VERSION 3.16)
  project(nasocheck_dsp C)
  set(CMAKE_C_STANDARD 99)
  add_library(nasocheck_dsp nasocheck_dsp.c)
  target_include_directories(nasocheck_dsp PUBLIC .)
  target_link_libraries(nasocheck_dsp m)
  add_executable(test_vectors test/test_vectors.c)
  target_link_libraries(test_vectors nasocheck_dsp)
endif()
