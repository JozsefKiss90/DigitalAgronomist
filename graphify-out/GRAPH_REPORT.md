# Graph Report - DigitalAgronomist  (2026-10-18)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 104 nodes · 195 edges · 7 communities (4 shown, 3 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 12 edges (avg confidence: 0.85)
- Token cost: 32,230 input · 101 output

## Graph Freshness
- Built from commit: `95480a02`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- KML Parcel Map App
- Main Window UI
- Bytecode Dump Verification
- Parcel SQLite Database
- Parcel Area Calculations
- Parcel Naming Dialog
- OpenCode Plugin Config

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 32 edges
2. `ParcelDatabase` - 12 edges
3. `cmd_verify()` - 8 edges
4. `NameDialog` - 6 edges
5. `parse_kml_file()` - 5 edges
6. `cmd_dump()` - 5 edges
7. `compare_one()` - 5 edges
8. `walk()` - 5 edges
9. `application_directory()` - 4 edges
10. `parse_manual_coordinates()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `MainWindow`  [EXTRACTED]
  DigitalAgronomist_GOLD_FIXED_SQLite_EXE.py → DigitalAgronomist_GOLD_FIXED_SQLite_EXE.py  _Bridges community 1 → community 0_

## Import Cycles
- None detected.

## Communities (7 total, 3 thin omitted)

### Community 0 - "KML Parcel Map App"
Cohesion: 0.10
Nodes (6): application_directory(), main(), parse_kml_file(), parse_manual_coordinates(), remove_duplicate_closing_point(), validate_rings()

### Community 2 - "Bytecode Dump Verification"
Cohesion: 0.18
Nodes (8): cmd_dump(), cmd_verify(), compare_one(), consts_sig(), keyed(), load_pyc(), norm_instrs(), walk()

### Community 4 - "Parcel Area Calculations"
Cohesion: 0.28
Nodes (4): haversine_distance_m(), ParcelRecord, polygon_area_m2(), total_area_m2()

### Community 6 - "OpenCode Plugin Config"
Cohesion: 0.25
Nodes (7): command, enabled, type, mcp, headroom, plugin, $schema

## Knowledge Gaps
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `Main Window UI` to `KML Parcel Map App`, `Parcel SQLite Database`, `Parcel Area Calculations`, `Parcel Naming Dialog`?**
  _High betweenness centrality (0.362) - this node is a cross-community bridge._
- **Should `KML Parcel Map App` be split into smaller, more focused modules?**
  _Cohesion score 0.10333333333333333 - nodes in this community are weakly interconnected._
- **Why does `ParcelDatabase` connect `Parcel SQLite Database` to `KML Parcel Map App`, `Main Window UI`, `Parcel Area Calculations`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Why does `NameDialog` connect `Parcel Naming Dialog` to `KML Parcel Map App`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._