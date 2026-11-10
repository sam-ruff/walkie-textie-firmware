# Hardware design

The board being worked on is the LoRa sensor node in `v3/kicad/` (V3.1). Its
own README says how to rebuild it and what to check before ordering, and
`CE_TESTING.md` beside it is how to run the compliance tests. No board has
been made from it yet.

`v3/` also holds the handover brief and the outside designer's drops that
V3.1 grew from. `archive/` holds the earlier radio boards and the scripts
that rebuilt the first of them. Nothing in there is current.

`CLAUDE.md` is the working log: what is settled and why, and the mistakes
made on the way.

KiCad 9 or newer is needed. The V3.1 tools use KiCad's `pcbnew` Python module
and were written against KiCad 10.0.8.
