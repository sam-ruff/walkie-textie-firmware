//! Factory test mode: the test signals the transmitter can send, and the commands that ask for them.
//!
//! Radio type-approval measurements (frequency error, occupied bandwidth,
//! radiated power, spurious emissions) need the transmitter on continuously,
//! which normal traffic never does. Others (transient power, behaviour as the
//! battery falls, every receiver test) need a steady run of identical packets.
//! This module only exists in builds made with the `factory-test` feature, so
//! firmware that ships cannot enter it.

/// Bytes in a test packet: the 511-bit sequence, and one bit more.
pub const TEST_PACKET_LEN: usize = 64;

/// The payload of a test packet: the 511-bit pseudo-random sequence of
/// ITU-T O.153 (x^9 + x^5 + 1), which EN 300 220-2 prefers as test data.
pub fn test_packet() -> [u8; TEST_PACKET_LEN] {
    let mut register: u16 = 0x1FF;
    let mut packet = [0u8; TEST_PACKET_LEN];
    for byte in packet.iter_mut() {
        for _ in 0..8 {
            *byte = (*byte << 1) | (register & 1) as u8;
            let feedback = (register ^ (register >> 4)) & 1;
            register = (register >> 1) | (feedback << 8);
        }
    }
    packet
}

/// The signal the transmitter sends while it is held on.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TestSignal {
    /// Unmodulated carrier at the configured frequency and power.
    Carrier,
    /// Continuous LoRa preamble with the configured bandwidth and spreading factor.
    Modulated,
}

/// A factory test command: one character on the debug serial port.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TestCommand {
    /// Hold the transmitter on with this signal until told to stop.
    Hold(TestSignal),
    /// Send test packets, one after another, until told to stop.
    Packets,
    /// Stop transmitting and go back to normal operation.
    Stop,
}

impl TestCommand {
    /// `c` carrier, `m` modulated, `p` packets, `s` stop, in either case. Anything else is not a command.
    pub fn from_byte(byte: u8) -> Option<Self> {
        match byte.to_ascii_lowercase() {
            b'c' => Some(Self::Hold(TestSignal::Carrier)),
            b'm' => Some(Self::Hold(TestSignal::Modulated)),
            b'p' => Some(Self::Packets),
            b's' => Some(Self::Stop),
            _ => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn letters_map_to_commands_in_either_case() {
        assert_eq!(TestCommand::from_byte(b'c'), Some(TestCommand::Hold(TestSignal::Carrier)));
        assert_eq!(TestCommand::from_byte(b'C'), Some(TestCommand::Hold(TestSignal::Carrier)));
        assert_eq!(TestCommand::from_byte(b'm'), Some(TestCommand::Hold(TestSignal::Modulated)));
        assert_eq!(TestCommand::from_byte(b'M'), Some(TestCommand::Hold(TestSignal::Modulated)));
        assert_eq!(TestCommand::from_byte(b'p'), Some(TestCommand::Packets));
        assert_eq!(TestCommand::from_byte(b'P'), Some(TestCommand::Packets));
        assert_eq!(TestCommand::from_byte(b's'), Some(TestCommand::Stop));
        assert_eq!(TestCommand::from_byte(b'S'), Some(TestCommand::Stop));
    }

    #[test]
    fn test_packet_starts_with_the_published_sequence() {
        assert_eq!(test_packet()[..8], [0xFF, 0x83, 0xDF, 0x17, 0x32, 0x09, 0x4E, 0xD1]);
    }

    #[test]
    fn test_packet_carries_one_whole_period_of_the_sequence() {
        let packet = test_packet();
        let bit = |index: usize| (packet[index / 8] >> (7 - index % 8)) & 1;

        // A maximal-length sequence of 511 bits has 256 ones, and then it starts again.
        assert_eq!((0..511).filter(|&index| bit(index) == 1).count(), 256);
        assert_eq!(bit(511), bit(0));
    }

    #[test]
    fn line_endings_and_other_bytes_are_ignored() {
        for byte in [b'\r', b'\n', b' ', b'x', 0x00, 0xFF] {
            assert_eq!(TestCommand::from_byte(byte), None);
        }
    }
}
