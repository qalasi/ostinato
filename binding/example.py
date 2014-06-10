#! /usr/bin/env python

# standard modules
import logging
import os
import sys
import time

# ostinato modules - prepend 'ostinato.' to the module names when using
# an installed package i.e ostinato.core and ostinato.protocols.xxx
from core import ost_pb, DroneProxy
from protocols.mac_pb2 import mac
from protocols.ip4_pb2 import ip4, Ip4

# initialize defaults
host_name = '127.0.0.1'
tx_port_number = 0
rx_port_number = 0

# setup logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

s = raw_input('Drone\'s Hostname/IP [%s]: ' % (host_name))
host_name = s or host_name

drone = DroneProxy(host_name)

try:
    # connect to drone
    log.info('connecting to drone(%s:%d)' 
            % (drone.hostName(), drone.portNumber()))
    drone.connect()

    # retreive port id list
    log.info('retreiving port list')
    port_id_list = drone.getPortIdList()

    # retreive port config list
    log.info('retreiving port config for all ports')
    port_config_list = drone.getPortConfig(port_id_list)

    # print port list and get tx/rx port id 
    print 'Port List'
    print '---------'
    for port in port_config_list.port:
        print '%d.%s (%s)' % (port.port_id.id, port.name, port.description) 
        # use a loopback port as default tx/rx port 
        if ('lo' in port.name or 'loopback' in port.description.lower()):
            tx_port_number = port.port_id.id
            rx_port_number = port.port_id.id

    p = raw_input('Tx Port Id [%d]: ' % (tx_port_number))
    if p:
        tx_port_number = int(p)

    p = raw_input('Rx Port Id [%d]: ' % (rx_port_number))
    if p:
        rx_port_number = int(p)

    tx_port = ost_pb.PortIdList()
    tx_port.port_id.add().id = tx_port_number;

    rx_port = ost_pb.PortIdList()
    rx_port.port_id.add().id = rx_port_number;

    # add a stream
    stream_id = ost_pb.StreamIdList()
    stream_id.port_id.CopyFrom(tx_port.port_id[0])
    stream_id.stream_id.add().id = 1
    log.info('adding tx_stream %d' % stream_id.stream_id[0].id)
    drone.addStream(stream_id)

    # configure the stream
    stream_cfg = ost_pb.StreamConfigList()
    stream_cfg.port_id.CopyFrom(tx_port.port_id[0])
    s = stream_cfg.stream.add()
    s.stream_id.id = stream_id.stream_id[0].id
    s.core.is_enabled = 1
    s.control.num_packets = 5

    p = s.protocol.add()
    p.protocol_id.id = ost_pb.Protocol.kMacFieldNumber
    p.Extensions[mac].dst_mac = 0x001122334455
    p.Extensions[mac].src_mac = 0x00aabbccddee

    p = s.protocol.add()
    p.protocol_id.id = ost_pb.Protocol.kEth2FieldNumber

    p = s.protocol.add()
    p.protocol_id.id = ost_pb.Protocol.kIp4FieldNumber
    p.Extensions[ip4].src_ip = 0x01020304
    p.Extensions[ip4].dst_ip = 0x05060708
    p.Extensions[ip4].dst_ip_mode = Ip4.e_im_inc_host

    s.protocol.add().protocol_id.id = ost_pb.Protocol.kUdpFieldNumber
    s.protocol.add().protocol_id.id = ost_pb.Protocol.kPayloadFieldNumber

    log.info('configuring tx_stream %d' % stream_id.stream_id[0].id)
    drone.modifyStream(stream_cfg)

    # clear tx/rx stats
    log.info('clearing tx/rx stats')
    drone.clearStats(tx_port)
    drone.clearStats(rx_port)

    # start capture and transmit
    log.info('starting capture')
    drone.startCapture(rx_port)
    time.sleep(1)
    log.info('starting transmit')
    drone.startTx(tx_port)

    # wait for transmit to finish
    log.info('waiting for transmit to finish ...')
    time.sleep(7)

    # stop transmit and capture
    log.info('stopping transmit')
    drone.stopTx(tx_port)
    log.info('stopping capture')
    drone.stopCapture(rx_port)

    # get tx/rx stats
    log.info('retreiving stats')
    tx_stats = drone.getStats(tx_port)
    rx_stats = drone.getStats(rx_port)

    #log.info('--> (tx_stats)' + tx_stats.__str__())
    #log.info('--> (rx_stats)' + rx_stats.__str__())
    log.info('tx pkts = %d, rx pkts = %d' % 
            (tx_stats.port_stats[0].tx_pkts, rx_stats.port_stats[0].rx_pkts))

    # retrieve and dump received packets
    log.info('getting Rx capture buffer')
    buff = drone.getCaptureBuffer(rx_port.port_id[0])
    drone.saveCaptureBuffer(buff, 'capture.pcap')
    log.info('dumping Rx capture buffer')
    os.system('tshark -r capture.pcap')
    os.remove('capture.pcap')

    # delete streams
    log.info('deleting tx_stream %d' % stream_id.stream_id[0].id)
    drone.deleteStream(stream_id)

    # bye for now
    drone.disconnect()

except Exception, ex:
    log.exception(ex)
    sys.exit(1)
