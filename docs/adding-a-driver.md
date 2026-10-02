# Adding a driver

A driver is how the bridge talks to one kind of gear. The interface is small
(`mackie/bridge/drivers/__init__.py`):

```python
read(target)          -> 0..1, or raises Unsupported
write(target, value)
toggle(target)        -> the new state
scenes()              -> list of names
load_scene(index)     -> the name loaded
```

A driver also declares **which buttons it knows what to do with**:

```python
class HD8(Driver):
    BUTTONS = {"rec": "scene"}                    # R n loads the n-th scene
                                                  # of the bank's scene list

class AppVolume(Driver):
    BUTTONS = {"play": "playpause", "stop": "pause",
               "forward": "next track", "rewind": "previous track"}
```

The bridge uses those whenever the profile says nothing, so a profile never has
to repeat what a driver already knows — and a bank made of gear that has no
transport simply has dead transport buttons. `"scene"` is the one special
value: it means `load_scene()`. Anything else is passed to `command()`.

Rules that came out of real bugs:

- **Raise `Unsupported`, never crash.** The bridge logs it and carries on. One
  parameter the device refuses must not abort a whole solo.
- **Say *why* it is unsupported.** `mac` answers "the Mac's default output has no
  system-controlled volume (an audio interface is selected)" instead of a
  stack trace — that message is the diagnosis.
- **Take the connection by injection.** `HD8(client=...)` is what makes the
  tests run with no hardware; build the real one only when nothing is passed.
- **Clamp what you write.** The bridge sends 0..1; the device decides what that
  means.

Register it in `drivers.build()` and add a test with a fake client, like
`tests/test_bridge_drivers.py`.

## Banks that cannot be written down (`live_faders`)

Some gear has no fixed channel list: OpenRig's mixer strips change with the
project and the chains that are open, so any bank naming them in the YAML goes
stale the moment another project is loaded. A driver for gear like that
implements

```python
live_faders(which)    -> {position: fader-dict}, or raises Unsupported
```

and its `DEFAULT_BANKS` entry carries `live: <which>` instead of `faders:`
(`openrig` uses `out` and `in`, giving the banks *OpenRig OUT* and
*OpenRig IN*). The daemon then asks the driver on entering the bank and once a
second (`refresh_live`), and a failure is logged, not fatal — the bank just
keeps the faders it had. `describe` prints `live` where a static bank prints a
fader count.

The default is `Unsupported`: a driver whose channels *are* stable should keep
listing them in `DEFAULT_BANKS`, which costs nothing per second.
