#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright(C) 2020-2022 Intel Corporation
# Authors:
#   Hector Blanco Alcaine

""" Module proxy

This module implements the client side for the system service dealing with the
application requests to guarantee deterministic QoS.

   * class ServiceProxy

Client and server side exchange messages using the protocol defined in the
file ipc.proto
"""




import array
import socket

from .common import Check

from .ipc_pb2 import StreamQosRequest
from .ipc_pb2 import StreamQosResponse


_SERVICE_UNIX_DOMAIN_SOCKET='/var/run/detd/detd_service.sock'




class ServiceProxy:

    def __init__(self):

        if not Check.is_valid_unix_domain_socket(_SERVICE_UNIX_DOMAIN_SOCKET):
            raise TypeError

        self.uds_address = _SERVICE_UNIX_DOMAIN_SOCKET

        self.setup_socket()


    def __del__(self):
        self.sock.close()


    def setup_socket(self):

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind("")


    def send(self, message):

        try:
            self.sock.sendto(message, self.uds_address)

        except:
            raise

#        finally:
#            self.sock.close()


    def recv(self):
        message, addr = self.sock.recvfrom(1024)

        return message


    def recv_fd(self, msglen):
        fds = array.array("i")   # Array of ints
        maxfds = 1
        msg, ancdata,flags, addr = self.sock.recvmsg(msglen, socket.CMSG_LEN(maxfds * fds.itemsize))
        for cmsg_level, cmsg_type, cmsg_data in ancdata:
            if cmsg_level == socket.SOL_SOCKET and cmsg_type == socket.SCM_RIGHTS:
                # Append data, ignoring any truncated integers at the end.
                fds.frombytes(cmsg_data[:len(cmsg_data) - (len(cmsg_data) % fds.itemsize)])
        return msg, list(fds)



    def send_qos_request(self, configuration, setup_socket):
        request = StreamQosRequest()
        request.interface = configuration.interface.name
        request.period = configuration.traffic.interval
        request.size = configuration.traffic.size
        request.dmac = configuration.stream.addr
        request.vid = configuration.stream.vid
        request.pcp = configuration.stream.pcp
        request.txmin = configuration.stream.txoffset
        request.txmax = configuration.stream.txoffset
        request.setup_socket = setup_socket

        message = request.SerializeToString()
        self.send(message)


    def receive_qos_response(self):
        message = self.recv()

        response = StreamQosResponse()
        response.ParseFromString(message)

        return response


    def receive_qos_socket_response(self):
        sock = self.sock

        message, fds = self.recv_fd(1024)
        response = StreamQosResponse()
        response.ParseFromString(message)

        s = socket.socket(fileno=fds[0])

        return response, s


    def setup_talker_socket(self, configuration):

        self.send_qos_request(configuration, setup_socket=True)
        status, sock = self.receive_qos_socket_response()

        if not status.ok:
            # FIXME handle error
            return None

        return sock


    def setup_talker(self, configuration):

        self.send_qos_request(configuration, setup_socket=False)
        response = self.receive_qos_response()

        if not response.ok:
            # FIXME handle error
            return None

        vlan_interface = response.vlan_interface
        soprio = response.socket_priority

        return vlan_interface, soprio
