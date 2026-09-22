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
