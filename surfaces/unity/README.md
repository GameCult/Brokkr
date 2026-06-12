# Brokkr Unity Adapter

This package lets the Unity Editor publish a host snapshot to the local Brokkr
daemon.

## Install By Local Path

Add this package to a Unity project's `Packages/manifest.json`:

```json
"com.gamecult.brokkr": "file:E:/Projects/Brokkr/surfaces/unity/Packages/com.gamecult.brokkr"
```

Then open `GameCult > Brokkr`.

## Local Smoke

Start the daemon:

```powershell
cargo run -p brokkr-daemon -- serve
```

In Unity:

1. Open `GameCult > Brokkr`.
2. Leave HTTP endpoint as `http://127.0.0.1:8798`.
3. Click `Ping Brokkr`.
4. Click `Capture Snapshot`.
5. Click `Publish Snapshot`.

The daemon should retain the latest Unity snapshot at:

```text
http://127.0.0.1:8798/hosts
```

The Unity plugin is still an adapter. Brokkr owns the Verse-facing provider and
receipt lane; Unity owns Unity editor truth.
