from structures.core import BitFieldStruct, Bit, BitPadding, Struct, Integer, BuildingError, ParsingError


def test_bitfieldstruct():

    data = b'\x33\x44\xF0\xFF'
    something_value_little_endian = 0x4433

    class MyBitfields(BitFieldStruct):
        foo = Bit(1)
        _ = BitPadding(3)
        bar = Bit(3)
        overflow = Bit(4)   # over byte boundary

    b = MyBitfields()
    print('instance:', b)

    try:
        b.build({'foo': 0b11, 'bar': 0b101, 'overflow': 0b1111})
    except Exception as e:
        assert isinstance(e, BuildingError)
        print('ParsingError catched:', e)

    builded_full = b.build({'foo': 0, 'bar': 0b101, 'overflow': 0b1111})
    # leave out foo, it shall be handled as 0.
    builded_partial = b.build({'bar': 0b101, 'overflow': 0b1111})
    assert builded_full == builded_partial

    builded = b.build({'foo': 1, 'bar': 0b101, 'overflow': 0b1111})
    print('builded:', builded)
    assert b.sizeof() == 2
    assert int.from_bytes(builded, 'little') == 0b11111010001
    parsed = b.parse(b'\xF0\xFF')
    print('parsed:', parsed)
    assert 'foo' in parsed
    assert 'bar' in parsed
    assert 'overflow' in parsed
    assert '_' not in parsed
    assert parsed['foo'] == 0b0
    assert parsed['bar'] == 0b111
    assert parsed['overflow'] == 0b1111

    class MyContainerStruct(Struct):
        something = Integer(2, 'little')
        bitfields = MyBitfields(embedded=True)

    x = MyContainerStruct()
    assert x.sizeof() == 4
    parsed = x.parse(data)
    assert parsed['something'] == something_value_little_endian

    try:
        # try to feed not enough data
        b.parse(b'\xff')
    except Exception as e:
        assert isinstance(e, ParsingError)
        print('ParsingError catched:', e)
