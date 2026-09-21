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

Rules that came out of real bugs:

- **Raise `Unsupported`, never crash.** The bridge logs it and carries on. One
  parameter the device refuses must not abort a whole solo.
- **Say *why* it is unsupported.** `mac` answers "a saída padrão do Mac não tem
  volume controlável pelo sistema (interface de áudio selecionada)" instead of
  a stack trace — that message is the diagnosis.
- **Take the connection by injection.** `HD8(client=...)` is what makes the
  tests run with no hardware; build the real one only when nothing is passed.
- **Clamp what you write.** The bridge sends 0..1; the device decides what that
  means.

Register it in `drivers.build()` and add a test with a fake client, like
`tests/test_bridge_drivers.py`.
