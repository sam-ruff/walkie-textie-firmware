# Future work: automated hardware test harness

Implement a build, flash, recover and test loop so an AI coding environment or
CI job can validate firmware on physical boards without direct USB access.
This is a proposal inspired by the supplied description of Embedded-AI-Harness
and the video *This AI Doesn't Just Write Code - It Tests Real Hardware!*.
The upstream repository and video URL still need recording; the API paths below
are proposed interfaces, not verified claims about that framework.

## Build separately from the test bench

Build this project's Rust/Embassy firmware with its ESP toolchain on Sam's
self-hosted Linux runners (`runs-on: [self-hosted, sophie]`). All CI stages,
including hardware tests, must use the local self-hosted pool. If capacity is
unavailable, leave the job queued or disabled; never fall back to GitHub-hosted
runners. This project does not need the example's ESP-IDF build pipeline.

Publish an immutable artifact bundle identified by commit SHA, with checksums,
board target, tool versions and everything required to flash. Include the
firmware ELF or correctly packaged flash images and the silent bootloader:
`espflash.toml` references a gitignored file under `bootloader/build/` that will
otherwise be missing on a fresh machine. Validate the bundle before deployment.

## Raspberry Pi test bench

Use an Ethernet-connected Raspberry Pi with USB access to the target boards and
a BLE adapter for Bluetooth tests. Run a small authenticated local API service
that retrieves or receives the build artifacts and owns the flashing and test
processes. The coding environment only needs network access to this service.

Proposed endpoints:

- `POST /api/flash`: submit an artifact identifier and a registered target board;
  return a job identifier for flashing, rebooting and testing.
- `POST /api/serial/recover`: recover a registered board's programming connection
  and report whether the bootloader is reachable.
- `GET /api/jobs/{id}`: return progress, stage results and links to captured logs.

Keep the API on the test bench network, restrict it to registered devices and
trusted artifacts, and lock each board for the whole flash/test cycle. Use
timeouts and bounded retries so concurrent requests or a stuck board cannot
leave a job running indefinitely. If implemented in Python, use FastAPI,
Pydantic, uv and Ruff, with injected hardware adapters and pytest tests.

## Flash and recovery cycle

Validate the artifact and target identity, release serial readers, enter the
bootloader and invoke `espflash` using the packaged inputs. `esptool` is an
alternative if the image layout is explicitly defined; `pyserial` alone is not
a flashing implementation.

Provide remote BOOT/EN control through suitable GPIO wiring, or RTS/DTR where
the board's serial interface supports it. Confirm the actual board wiring before
choosing a recovery sequence. Native USB behaviour must be tested on the bench.

The existing firmware guidance requires a power cycle after flashing to leave
ROM download mode. Include remotely switched power and verify that USB or another
supply cannot keep the board powered. Release BOOT before restoring power, wait
for application enumeration, then rediscover its ports by stable board identity.
Do not assume `/dev/ttyACM*` numbering survives a reset.

Capture the separate data and debug CDC interfaces. Confirm a valid host-link
version response before starting the test suite. On failure, preserve flash and
boot logs, attempt bounded recovery, and report the failing stage distinctly
from a test assertion failure.

## Reuse the existing hardware tests

Start with the host-side tools in `integration_tests/`:

- Serial version queries, invalid commands and repeated exchanges.
- BLE host-link exchanges and reconnect behaviour.
- Two-board LoRa delivery, then BLE-to-serial and BLE-to-BLE round trips.
- USB CDC boundary regression coverage, including encoded responses at a
  64-byte boundary that must arrive without unrelated traffic flushing them.

The existing Cargo aliases target `x86_64-unknown-linux-gnu`. Build host test
executables for the Pi's architecture, or run them on a suitable self-hosted
machine with access to the required USB/BLE interfaces. Select boards explicitly
so a test cannot attach to another job's device.

Wi-Fi captive portal and MQTT checks from the supplied example belong to projects
that expose those features. Here the initial scope is USB, BLE and LoRa. Keep
test orchestration outside production firmware and mock external services and
hardware adapters in unit tests; run physical integration tests separately.

## Completion criteria

A single submitted artifact should flash designated boards, power-cycle them,
verify application startup, run the selected hardware suite and return a clear
pass/fail result without manual unplugging. Retain the commit SHA, artifact
checksums, device identities, serial logs, recovery attempts and test results
with each run so the coding agent can diagnose failures and propose a fix.

Before calling the harness ready, demonstrate successful operation and bounded
failure handling for an unavailable board, corrupt artifact, failed flash,
stuck bootloader and failed test. Confirm the Pi architecture, power switching,
BOOT/EN wiring and two-board/BLE capacity on the actual bench.
