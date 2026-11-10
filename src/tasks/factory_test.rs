//! Factory test mode: sends the test signals radio type-approval measurements need.
//!
//! Only in builds made with the `factory-test` feature. Commands are single
//! characters typed into the debug serial port: `c` for an unmodulated
//! carrier, `m` for continuous LoRa modulation, `p` for test packets, `s` to
//! stop. While a test signal is being sent the radio does not receive and
//! host commands wait.

use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::channel::Channel;
use embassy_time::{with_timeout, Duration};
use embassy_usb::class::cdc_acm::Receiver;
use esp_hal::otg_fs::asynch::Driver;

use crate::lora::test_mode::{test_packet, TestCommand, TestSignal};
use crate::lora::traits::{LoraRadio, TestTransmitter};

/// Commands from the debug port to the LoRa task, which owns the radio.
pub static TEST_CHANNEL: Channel<CriticalSectionRawMutex, TestCommand, 4> = Channel::new();

/// Silence between one test packet and the next.
const PACKET_GAP: Duration = Duration::from_secs(1);

/// Read test commands from the debug serial port and queue them for the LoRa task.
pub async fn test_command_task(mut receiver: Receiver<'static, Driver<'static>>) {
    let mut buf = [0u8; 64];
    loop {
        receiver.wait_connection().await;
        while let Ok(len) = receiver.read_packet(&mut buf).await {
            for command in buf[..len].iter().filter_map(|byte| TestCommand::from_byte(*byte)) {
                TEST_CHANNEL.send(command).await;
            }
        }
    }
}

/// Send test signals, starting with what `first` asks for, until a stop arrives.
pub async fn run_until_stopped(radio: &mut (impl LoraRadio + TestTransmitter), first: TestCommand) {
    let mut command = first;
    loop {
        command = match command {
            TestCommand::Hold(signal) => hold(radio, signal).await,
            TestCommand::Packets => send_packets(radio).await,
            TestCommand::Stop => break,
        };
    }
    if radio.set_standby().await.is_err() {
        crate::debug!("Factory test: could not stop the transmitter");
        return;
    }
    crate::debug!("Factory test: stopped");
}

/// Hold the transmitter on with `signal` until the next command, which is returned.
async fn hold(radio: &mut impl TestTransmitter, signal: TestSignal) -> TestCommand {
    if radio.hold_transmitter(signal).await.is_err() {
        crate::debug!("Factory test: could not start the transmitter");
        return TestCommand::Stop;
    }
    crate::debug!("Factory test: transmitting {:?}, send 's' to stop", signal);
    TEST_CHANNEL.receive().await
}

/// Send test packets, a gap apart, until the next command, which is returned.
async fn send_packets(radio: &mut impl LoraRadio) -> TestCommand {
    let packet = test_packet();
    let mut sent: u32 = 0;
    crate::debug!("Factory test: sending {} byte test packets, send 's' to stop", packet.len());
    loop {
        if radio.transmit(&packet).await.is_err() {
            crate::debug!("Factory test: test packet {} was not sent", sent + 1);
            return TestCommand::Stop;
        }
        sent += 1;
        crate::debug!("Factory test: {} test packets sent", sent);
        if let Ok(command) = with_timeout(PACKET_GAP, TEST_CHANNEL.receive()).await {
            return command;
        }
    }
}
