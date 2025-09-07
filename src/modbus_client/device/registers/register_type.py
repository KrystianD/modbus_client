from enum import Enum


class RegisterType(str, Enum):
    S16 = 'int16'
    U16 = 'uint16'
    S32BE = 'int32be'
    S32LE = 'int32le'
    U32BE = 'uint32be'
    U32LE = 'uint32le'
    S64BE = 'int64be'
    S64LE = 'int64le'
    U64BE = 'uint64be'
    U64LE = 'uint64le'
    F32BE = 'float32be'
    F32LE = 'float32le'
    ENUM = 'enum'
    BOOL = 'bool'
    FLAGS = 'flags'
