# Brokkr stores on MessagePack payloads: target

This is campaign `brokkr-msgpack`. The mind holds its rulings, its spec and its
verdicts. This page holds only the rationale and the shape the cut must produce.

## Why

cultcache-py's payload default moves from JSON to MessagePack. The change is in
CultLib branch `hands/py-msgpack-default`, which Soul held at `d9f73281`. Under the
operator's ruling `cultlib-gaps:ruling:py-migration-shape-ruled`, `convert` writes a
new MessagePack store and never writes its source.

Brokkr loads cultcache-py from the CultLib checkout its settings name
(`blender_target.py`). It does not install a pinned package. So the moment CultLib's
main takes that branch, the Blender bridge starts writing MessagePack payloads, and
Brokkr's daemon must read them. The two changes therefore land together.

## Design truths the cut must produce

- **One payload format.** Every store the daemon and the Blender bridge write carries
  MessagePack payloads. The daemon reads exactly one MessagePack value per payload and
  refuses trailing bytes.
- **Conversion never writes a source.** An existing JSON store is converted into a new
  file, with `cultcache_py.convert` for the bridge's store and a one-shot daemon
  subcommand for the daemon's receipts. The JSON original is kept for as long as the
  operator wants it.
- **The bridge refuses a cultcache-py without `convert`.** A checkout older than the
  branch is refused at load, so it can never write a format the daemon cannot read.
- **One operator window.**
  1. Close Blender and stop sync.
  2. Merge CultLib's branch to main and move the checkout to it.
  3. Merge Brokkr.
  4. Build the daemon.
  5. Convert, open and swap in any stores that exist.
  6. Restart.

  None existed on 2026-10-14.

## Not in scope

- The Unity mirror's directory store, against the daemon's single-file open (X1 in
  `docs/brokkr-adoption-cut.md`).
- The Blender bridge's move to a directory store, under ruling
  `brush-tree:ruling:blender-transport-ruled`. That move belongs to campaign
  `brush-tree`, and it lands after this cut.
- Bumping the daemon's cultcache-rs pin.

## Evidence

Imagination's probes are recorded in the cut spec and its report. They show that
converting a bridge store with the eight definitions preserves every record and
leaves the source untouched. The daemon baseline is 20 of 20 tests passing at `f97d4dc`.
