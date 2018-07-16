"""
Raspberry Pi EEPROM as defined in https://github.com/raspberrypi/hats/blob/master/eeprom-format.md
"""

import uuid
import structures as st

import crcmod


class VendorInfoAtomData(st.Struct):
    uuid = st.Bytes(16)
    pid = st.Integer(2, byteorder='little')
    pver = st.Integer(2, byteorder='little')
    vslen = st.Integer(1)
    pslen = st.Integer(1)
    vstr = st.Contextual(st.String, lambda ctx: ctx['vslen'])
    pstr = st.Contextual(st.String, lambda ctx: ctx['pslen'])


class GPIOMapAtomData(st.Struct):
    bank_drive = st.BitFields('hysteresis:2, slew:2, drive:4')
    power = st.BitFields('_reserved:6, back_power:2')
    pins = st.RepeatExactly(
        st.BitFields('is_used:1, pulltype:2, _reserved: 2, func_sel:3'),
        28
    )


class Atom(st.Struct):
    type = st.Integer(2, byteorder='little')
    count = st.Integer(2, byteorder='little')
    dlen = st.Integer(4, byteorder='little')
    #data = st.Contextual(st.Bytes, lambda ctx: ctx['dlen']-2)
    data = st.Switch(
		lambda ctx: ctx['type'],
		cases={
			1: VendorInfoAtomData(),
			2: GPIOMapAtomData(),
		}
	)
    crc = st.Bytes(2)


class EEPROMData(st.Struct):
    signature = st.Const(b'R-Pi')
    version = st.Integer(1, byteorder='little')
    _rsvd0 = st.Integer(1, byteorder='little')
    numatoms = st.Integer(2, byteorder='little')
    eeplen = st.Integer(4, byteorder='little')
    atoms = st.Contextual(
        lambda n: st.RepeatExactly(Atom(), n),
        lambda ctx: ctx['numatoms'],
    )



atom_data = dict(uuid=uuid.uuid4().bytes, pid=0, pver=0, vslen=6, pslen=7, vstr=b'vendor', pstr=b'product')
atom_data_built = VendorInfoAtomData().build(atom_data)
atom = dict(type=1, count=0, dlen=len(atom_data_built)+2, data=atom_data, crc=b'00')
atom_built = Atom().build(atom)
crc_data = atom_built[:-2]
crc = crcmod.predefined.mkCrcFun('crc-16')(crc_data)
atom.update(dict(crc=crc.to_bytes(2, 'little')))

eep = dict(version=1, _rsvd0=0, numatoms=1, eeplen=1, atoms=[atom])
eep_built = EEPROMData().build(eep)
eep.update(dict(eeplen=len(eep_built)))
print(eep)

