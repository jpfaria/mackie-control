# Pending

What has been asked for and is not done yet, so it survives the session that
heard it.

- **An `openrig` driver** (asked 2026-09-22). OpenRig exposes its whole
  command set as MCP tools over Streamable HTTP at `127.0.0.1:4123`
  (`OpenRig/docs/mcp.md`), the same surface Claude drives — so the driver is
  an MCP client, not a new protocol. Before writing it: list the live tools
  (`tools/list`) and resources, and measure a chain-volume write and read back
  on the running app.
- **MK-300 and Ampero II over Bluetooth** (asked 2026-09-22). Both pedals take
  USB or BLE, and the port name changes with the transport, as on the
  SMC-Mixer. The drivers only look for the USB name today (`USB Composite
  Device`, `Ampero II Stage MIDI`). Measure each pedal's BLE port name, and
  whether its SysEx survives BLE at all, before adding it.
- **Starting the arrows from the device's own scene, on the hardware.** The
  MK-300 (`current_preset_index`) and the Ampero (global page 9) can say which
  preset or patch is loaded, and the bridge now starts from it. Not yet
  measured on the pedals: the first try hit the MK-300 unplugged and the
  Ampero port already held by the running bridge ("input overrun"). The HD 8
  cannot say at all — no scene parameter in its state — so there the arrows
  start from the scene the bridge itself last loaded, kept across restarts.
