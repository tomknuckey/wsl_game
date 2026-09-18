## How to 

git tag -a v0.4.0 -m "Version 0.4.0"


git push origin v0.4.0


## Versioning

| Change                                         | Version | Example                             |
| ---------------------------------------------- | ------- | ----------------------------------- |
| **PATCH** — bug fix / tiny change              | `1.0.1` | Fix incorrect goal sharing          |
| **MINOR** — new functionality                  | `1.1.0` | Add player leaderboard              |
| **MAJOR** — significant change/breaking change | `2.0.0` | Completely change how scoring works |

Version log like this?

# Changelog

All notable changes to the WSL Game are documented here.

## [0.4.0] - 2026-09-20

### Added
- Added player leaderboard
- Added team leaderboard
- Added gameweek-by-gameweek results
- Added player statistics

### Changed
- Updated leaderboard to show total goals and points
- Improved calculation of shared goals

### Fixed
- Fixed duplicate player records in leaderboard

---

## [0.3.1] - 2026-09-17

### Fixed
- Fixed goal-sharing calculation when multiple players have selected the same scorer
- Fixed incorrect player ID mapping for transfers

---

## [0.3.0] - 2026-09-15

### Added
- Added WSL fixture data
- Added player selection functionality
- Added scoring calculation
- Added support for shared goals

### Changed
- Refactored scoring logic into separate functions
- Improved data validation

---

## [0.2.0] - 2026-09-10

### Added
- Added initial player database
- Added team database
- Added participant selections

---

## [0.1.0] - 2026-09-01

### Added
- Initial project structure
- Initial WSL player data
- Basic scoring prototype