import time


def open_serial(serial_module, port, baud):
    inst = serial_module.Serial(port=port, baudrate=baud, timeout=2)
    try:
        inst.write(b'*IDN?\n')
        inst.flush()
        time.sleep(0.3)
        idn = inst.readline().decode('utf-8', errors='ignore').strip()
        if not idn:
            time.sleep(0.3)
            idn = inst.readline().decode('utf-8', errors='ignore').strip()
        return inst, idn
    except Exception:
        try:
            inst.close()
        except Exception:
            pass
        raise


def open_visa(visa_module, ip, port):
    rm = visa_module.ResourceManager('@py')
    inst = None
    try:
        inst = rm.open_resource(f'TCPIP::{ip}::{port}::SOCKET', timeout=5000)
        inst.read_termination = '\n'
        inst.write_termination = '\n'
        return rm, inst, inst.query('*IDN?').strip()
    except Exception:
        close_resources(inst, rm)
        raise


def close_resources(inst, resource_manager=None):
    for resource in (inst, resource_manager):
        if resource is not None:
            try:
                resource.close()
            except Exception:
                pass
