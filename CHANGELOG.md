# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed

- Fixed sandbox startup crash when a read-only sub-mount exists under `/sandbox`
  during recursive `chown`. The supervisor now detects read-only mount points
  by parsing `/proc/self/mountinfo` and skips them during the ownership walk,
  preventing `EROFS` errors that previously caused pods to enter
  `CrashLoopBackOff`. If a path inside a read-only mount is encountered despite
  the pre-filter, a warning is logged and the walk continues rather than
  aborting.
