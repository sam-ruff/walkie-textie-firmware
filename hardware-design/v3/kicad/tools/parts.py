"""Every part of the corrected board, with what the board and the schematic both need.

design.PARTS restates only what changed for a part kept from the PCB_V3 drop;
this fills in the rest from the import model so both builders read one answer.
"""
import design

FIELDS = ("value", "lcsc", "mpn", "manufacturer")


def plain_value(value):
    """The drop writes resistor values with an ohm sign; fabrication tools want plain ASCII."""
    if value.endswith("Ω"):
        body = value[:-1]
        return body if body[-1:].isalpha() else body + "R"
    return value


def plain_maker(name):
    """The drop adds the maker's Chinese name in brackets, as in "SAMSUNG(三星)"; keep the first part."""
    return (name or "").split("(")[0].strip()


def footprint_id(footprint):
    """Library identifier as KiCad writes it. Names from KiCad's own library already carry theirs."""
    lib, name = footprint
    return name if lib == design.KICAD else f"{lib}:{name}"


def assembly_fields(part):
    """(name, value) of the fields that the schematic symbol and the footprint both carry for a part."""
    return [("LCSC", part["lcsc"]), ("MPN", part["mpn"]), ("Manufacturer", part["manufacturer"])]


def fitted(all_parts, order):
    """Designators of the parts one order has assembled: the default population with that order's changes."""
    changes = design.ORDERS[order]
    unknown = (set(changes.get("fit", [])) | set(changes.get("leave_out", []))) - set(all_parts)
    if unknown:
        raise SystemExit(f"order {order!r} names parts that are not on the board: {sorted(unknown)}")
    chosen = {ref for ref, part in all_parts.items() if not part["no_bom"] and not part["dnp"]}
    return (chosen | set(changes.get("fit", []))) - set(changes.get("leave_out", []))


def as_built(all_parts, order):
    """The parts as one order has them: `dnp` then says whether that order leaves a part off."""
    on = fitted(all_parts, order)
    return {ref: {**part, "dnp": not part["no_bom"] and ref not in on} for ref, part in all_parts.items()}


def resolve(model):
    delivered = {c["ref"]: c for c in model["comps"]}
    out = {}
    for ref, spec in design.PARTS.items():
        old = delivered[spec["was"]] if spec["was"] else None
        if old:
            footprint = spec.get("footprint", (design.LIB_V3, old["package"]))
            at = spec.get("at", tuple(old["at"]))
            rot = spec.get("rot", old["rot"])
            fields = {k: spec.get(k, old[k]) for k in FIELDS}
        else:
            footprint, at, rot = spec["footprint"], spec["at"], spec["rot"]
            fields = {k: spec.get(k, "") for k in FIELDS}
        out[ref] = {
            "ref": ref,
            "was": spec["was"],
            "delivered": old,
            "footprint": footprint,
            "fp_id": footprint_id(footprint),
            "at": at,
            "rot": rot,
            "value": plain_value(fields["value"]),
            "lcsc": fields["lcsc"] or "",
            "mpn": fields["mpn"] or "",
            "manufacturer": plain_maker(fields["manufacturer"]),
            "dnp": bool(spec.get("dnp")),
            "no_bom": bool(spec.get("no_bom")),
            # A part the assembler places from stock sent to it. `footprint_as` is the LCSC number whose
            # library footprint stands in for it where the assembler's own entry has none.
            "supplied": bool(spec.get("supplied")),
            "footprint_as": spec.get("footprint_as", ""),
            # {pad number here: [JLCPCB's numbers for that pad]} where its library numbers the part differently.
            "jlc_pads": spec.get("jlc_pads", {}),
            # mm of solder mask opening beyond each pad, where the board's own figure leaves too little mask between pads
            "mask_margin": spec.get("mask_margin"),
            # pads that a track reaches and the ground fill is kept off
            "track_only": tuple(spec.get("track_only", ())),
            "nets": spec["nets"],
        }
    return out
