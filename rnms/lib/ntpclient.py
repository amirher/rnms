# -*- coding: utf-8 -*-
#
# This file is part of the Rosenberg NMS
#
# Copyright (C) 2012 Craig Small <csmall@enc.com.au>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>
#
import asyncore
import socket
import struct
import datetime
import logging

logger = logging.getLogger('NTPClient')

""" NTP Client """

class NTPClientError(Exception):
    pass

class NTPClient():
    """
    NTP Client is the Base Class to make NTP control queries.
    Uses two dispatchers, one for each address family
    """
    address_families = [ socket.AF_INET, socket.AF_INET6 ]

    def __init__(self):
        self.dispatchers = { af : NTPDispatcher(af) for af in self.address_families}

    def get_peers(self, host, cb_fun, **kwargs):
        """
        Returns a list of peers to the callback function
        Returns true on success
        """
        query_packet = NTPControl()
        return self._send_message(host, query_packet, cb_fun, **kwargs)

    def get_peer_by_id(self, host, assoc_id, cb_fun, **kwargs):
        """
        Return the information known by the host for the specified peer
        """
        query_packet = NTPControl(opcode=2, assoc_id=assoc_id)
        return self._send_message(host, query_packet, cb_fun, **kwargs)

    def _send_message(self, host, request_packet, cb_fun, **kwargs):
        try:
            addrinfo = socket.getaddrinfo(host.mgmt_address, 123)[0]
        except socket.gaierror:
            return False
        addr_family, sockaddr = addrinfo[0], addrinfo[4]
        try:
            return self.dispatchers[addr_family].send_message(host,request_packet,cb_fun, **kwargs)
        except KeyError:
            logger.error('Cannot find dispatcher for address family {0}',addr_family)
            return False

    def poll(self):
        retval = False
        for dispatcher in self.dispatchers.values():
            if dispatcher.poll() == True:
                retval = True
        return retval

class NTPDispatcher(asyncore.dispatcher):
    """
    Dispatcher for each address family for NTP queries
    """
    timeout = 10

    def __init__(self, address_family):
        asyncore.dispatcher.__init__(self)
        self.create_socket(address_family, socket.SOCK_DGRAM)
        self.waiting_jobs = []
        self.sent_jobs = {}
        self.next_sequence = 0

    def handle_connect(self):
        pass

    def handle_close(self):
        self.close()

    def handle_read(self):
        recv_msg, recv_addr =  self.recvfrom(8192)
        logger.debug("Received message from %s", recv_addr)
        try:
            recv_job = self.sent_jobs[recv_addr]
        except KeyError:
            logger.warning("No job for %s", recv_addr)
        else:
            self._parse_response(recv_job, recv_msg, recv_addr)

    def writable(self):
        return (len(self.waiting_jobs) > 0)

    def handle_write(self):
        try:
            new_job = self.waiting_jobs.pop()
        except IndexError:
            return
        new_job['timeout'] = datetime.datetime.now() + datetime.timedelta(seconds=self.timeout)
        self.sent_jobs[new_job['sockaddr']] = dict(new_job)
        try:
            self.sendto(new_job['request_packet'].to_data(), new_job['sockaddr'])
        except socket.error as errmsg:
            logger.error("Socket error for sendto %s", new_job['sockaddr'])
            raise NTPClientError(errmsg)

    def _get_next_sequence(self):
        next_seq = self.next_sequence
        self.next_sequence += 1
        return next_seq

    def _parse_response(self, recv_job, recv_msg, recv_addr):
        """
        Calls the given callback with message and delets from sent queue
        """
        response_packet = recv_job['response_packet']
        if recv_msg is not None:
            response_packet.from_data(recv_msg)
        if response_packet.more == 0:
            recv_job['cb_fun'](recv_job['host'], response_packet, **recv_job['kwargs'])
            del(self.sent_jobs[recv_addr])

    def send_message(self, host, request_packet, cb_fun, **kwargs):
        try:
            addrinfo = socket.getaddrinfo(host.mgmt_address, 123)[0]
        except socket.gaierror:
            logging.warning("getaddrinfo error")
            return False
        sockaddr = addrinfo[4]
        request_packet.sequence = self._get_next_sequence()

        self.waiting_jobs.append({
            'host': host,
            'sockaddr': sockaddr,
            'request_packet': request_packet,
            'response_packet': NTPControl(),
            'cb_fun': cb_fun,
            'kwargs': kwargs})
        return True
    
    def poll(self):
        """
        Check pending and waiting jobs
        Returns true if there are things going on
        This method also checks timed out jobs
        """
        retval = False
        if self.waiting_jobs != []:
            retval = True
        now = datetime.datetime.now()
        for job in self.sent_jobs.values():
            if job['timeout'] < now:
                # Job timed out
                logger.debug('Job for %s timed out', job['sockaddr'])
                self._parse_response(job, None, job['sockaddr'])
            else:
                retval = True
        return retval


class NTPAssoc():
    """
    Class holding information about the NTP Associations
    """
    assoc_id = 0
    __PACKET_FORMAT = '!H B B'

    def from_data(self, data):
        unpacked = struct.unpack(self.__PACKET_FORMAT, data)
        self.assoc_id = unpacked[0]
        self.configured = unpacked[1] >> 7 & 0x1
        self.authentable = unpacked[1] >> 6 & 0x1
        self.authentic = unpacked[1] >> 5 & 0x1
        self.reach = unpacked[1] >> 4 & 0x1
        # bit 3 is reserved
        self.selection = unpacked[1] & 0x7

        self.event_counter = unpacked[2] >> 4 & 0xf
        self.event_code = unpacked[2] & 0xf

class NTPControl():
    leap = 0
    version = 2
    mode = 6

    response = 0
    error = 0
    more = 0

    leap_indicator = 0
    clock_source = 0
    event_counter = 0
    event_code = 0
    offset = 0
    count = 0

    __PACKET_FORMAT = "!B B H H H H H"

    def __init__(self, opcode=1, sequence=1, assoc_id=0):
        self.opcode = opcode
        self.sequence = sequence
        self.assoc_id = assoc_id
        self.peers = []
        self.assoc_data = {}

    def __repr__(self):
        return '<NTPControl seq={2} assoc_id={0} opcode={1}>'.format(self.assoc_id, self.opcode, self.sequence)

    def to_data(self):
        packed = struct.pack(self.__PACKET_FORMAT,
            (self.leap << 6 | self.version << 3 | self.mode),
            (self.response << 7 | self.error << 6 | self.more << 5 | self.opcode ),
            self.sequence,
            0,
            self.assoc_id,
            self.offset,
            self.count)
        return packed

    def from_data(self, data):
        header_len = struct.calcsize(self.__PACKET_FORMAT)
        flags1, flags2, self.sequence, status, self.assoc_id, self.offset, self.count = struct.unpack(self.__PACKET_FORMAT, data[0:header_len])
        self.leap = flags1 >> 6 & 0x3
        self.version = flags1 >> 3 & 0x7
        self.mode = flags1 & 0x7
        self.response = flags2 >> 7 & 0x1
        self.error = flags2 >> 6 & 0x1
        self.more = flags2 >> 5 & 0x1
        self.opcode = flags2 & 0x1f

        self.leap_indicator = status >> 14 & 0x3
        self.clock_source = status >> 8 & 0x3f
        self.event_counter = status >> 4 & 0xf
        self.event_code = status & 0xf

        if self.opcode == 1:
            for assoc_count in range(0, (self.count)/4):
                assoc = NTPAssoc()
                assoc.from_data(data[header_len+assoc_count*4:header_len+(assoc_count+1)*4])
                self.peers.append(assoc)
        elif self.opcode == 2:
            assoc_data = data[header_len:].split(",")
            self.assoc_data.update(dict([tuple(ad.strip().split("=")) for ad in data[header_len:].split(",") if ad.find("=") > -1]))

