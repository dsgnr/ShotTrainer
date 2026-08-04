//! Owned 8-bit image buffers passed between capture, transforms and detection.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PixelFormat {
    /// One byte per pixel.
    Grey,
    /// Three bytes per pixel in OpenCV's blue, green, red order.
    Bgr,
}

impl PixelFormat {
    pub fn channels(self) -> usize {
        match self {
            PixelFormat::Grey => 1,
            PixelFormat::Bgr => 3,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum FrameError {
    #[error("frame data has {actual} bytes, expected {expected}")]
    WrongLength { expected: usize, actual: usize },
    #[error("Unsupported rotation: {0}")]
    UnsupportedRotation(i32),
}

/// A row-major, tightly packed image. A frame with zero width or height is
/// valid and empty.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Frame {
    width: u32,
    height: u32,
    format: PixelFormat,
    data: Vec<u8>,
}

impl Frame {
    pub fn new(
        width: u32,
        height: u32,
        format: PixelFormat,
        data: Vec<u8>,
    ) -> Result<Self, FrameError> {
        let expected = width as usize * height as usize * format.channels();
        if data.len() != expected {
            return Err(FrameError::WrongLength {
                expected,
                actual: data.len(),
            });
        }
        Ok(Frame {
            width,
            height,
            format,
            data,
        })
    }

    /// For callers that built `data` with the right length themselves.
    pub(crate) fn from_parts(width: u32, height: u32, format: PixelFormat, data: Vec<u8>) -> Self {
        debug_assert_eq!(
            data.len(),
            width as usize * height as usize * format.channels()
        );
        Frame {
            width,
            height,
            format,
            data,
        }
    }

    pub fn filled(width: u32, height: u32, format: PixelFormat, value: u8) -> Self {
        let len = width as usize * height as usize * format.channels();
        Frame {
            width,
            height,
            format,
            data: vec![value; len],
        }
    }

    pub fn width(&self) -> u32 {
        self.width
    }

    pub fn height(&self) -> u32 {
        self.height
    }

    pub fn format(&self) -> PixelFormat {
        self.format
    }

    pub fn data(&self) -> &[u8] {
        &self.data
    }

    pub fn into_data(self) -> Vec<u8> {
        self.data
    }

    pub fn is_empty(&self) -> bool {
        self.data.is_empty()
    }
}
