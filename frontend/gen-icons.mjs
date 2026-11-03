import fs from 'fs';
import zlib from 'zlib';

const crcTable = new Array(256);
for (let i = 0; i < 256; i++) {
  let c = i;
  for (let j = 0; j < 8; j++) {
    c = (c & 1) ? (c >>> 1) ^ 0xEDB88320 : c >>> 1;
  }
  crcTable[i] = c >>> 0;
}

function crc32(buf) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < buf.length; i++) {
    let crc_ = (crc ^ buf[i]) & 0xFF;
    for (let j = 0; j < 8; j++) {
      crc_ = (crc_ & 1) ? (crc_ >>> 1) ^ 0xEDB88320 : crc_ >>> 1;
    }
    crc = (crc >>> 8) ^ crcTable[crc_];
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

function makeChunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const typeBuf = Buffer.from(type);
  const crcVal = crc32(Buffer.concat([typeBuf, data]));
  return Buffer.concat([
    len,
    typeBuf,
    data,
    Buffer.from([(crcVal >>> 24) & 0xFF, (crcVal >>> 16) & 0xFF, (crcVal >>> 8) & 0xFF, crcVal & 0xFF])
  ]);
}

function createPNG(size) {
  // IHDR chunk
  const ihdrData = Buffer.alloc(13);
  ihdrData.writeUInt32BE(size, 0);
  ihdrData.writeUInt32BE(size, 4);
  ihdrData[8] = 8;
  ihdrData[9] = 6;
  ihdrData[10] = 0;
  ihdrData[11] = 0;
  ihdrData[12] = 0;

  // Create image data for solid color #863bff with full alpha
  const rowSize = 1 + size * 4;
  const imageData = Buffer.alloc(size * rowSize);
  for (let y = 0; y < size; y++) {
    imageData[y * rowSize] = 0; // filter type 0
    for (let x = 0; x < size; x++) {
      const offset = y * rowSize + 1 + x * 4;
      imageData[offset] = 0x86;
      imageData[offset + 1] = 0x3B;
      imageData[offset + 2] = 0xFF;
      imageData[offset + 3] = 0xFF;
    }
  }

  const idatData = zlib.deflateSync(imageData);

  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
    makeChunk('IHDR', ihdrData),
    makeChunk('IDAT', idatData),
    makeChunk('IEND', Buffer.alloc(0))
  ]);
}

const sizes = [192, 512];
for (const size of sizes) {
  const png = createPNG(size);
  fs.writeFileSync(`public/icon-${size}.png`, png);
  console.log(`Generated icon-${size}.png (${png.length} bytes)`);
}

console.log('Icon generation complete');