# -*- coding: utf-8 -*-
#
# This file is part of the RoseNMS
#
# Copyright (C) 2012-2014 Craig Small <csmall@enc.com.au>
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
# This poller is based upon the JFFNMS poller of the same name
# Copyright (C) <2002-2005> Javier Szyszlican <javier@szysz.com>

# For details on setting ip accounting up see
# http://www.cisco.com/en/US/tech/tk648/tk362/
#     technologies_configuration_example09186a0080094aa2.shtml

SAAGENT_BASE = (1, 3, 6, 1, 4, 1, 9, 9, 42, 1, 5, 2, 1)


def poll_cisco_saagent(poller_buffer, parsed_params, **kw):
    """
    Obtain data about the Cisco SA Agent.
    Parameters: <index>|<qtype>
      <index>: The SA Agent index
      <qtype>: query type, must be one of the keys in the table above
    """
    saagent_queries = {
        'fwd_jitter': ((8, 9, 13, 14),   cb_jitter),
        'bwd_jitter': ((18, 19, 23, 24),  cb_jitter),
        'packetloss': ((1, 2, 26, 27),  cb_packetloss),
        }

    try:
        index, qtype = parsed_params.split('|')
    except ValueError:
        kw['pobj'].logger.error('Need index|qtype')
        return False
    try:
        (queries, cb_fun) = saagent_queries[qtype]
    except KeyError:
        kw['pobj'].logger.errror('Bad query type %s', qtype)
        return False

    #req.oid_trim = 2
    oids = [SAAGENT_BASE + (x, int(index)) for x in queries]
    return kw['pobj'].snmp_engine.get_list(kw['attribute'].host, oids,
                                           cb_fun, **kw)


def cb_jitter(values, error, pobj, attribute, **kw):
    if values is None or len(values) != 4:
        pobj.poller_callback(attribute.id, None)
        return
    try:
        jitter = (int(values[1]) + int(values[3])) / \
            (int(values[0]) + int(values[2]))
    except (ZeroDivisionError, ValueError):
        jitter = 0
    pobj.poller_callback(attribute.id, jitter)


def cb_packetloss(values, error, pobj, attribute, **kw):
    if values is None or len(values) != 4:
        pobj.poller_callback(attribute.id, None)
        return
    nr = int(values[0])
    if nr == 0:
        pobj.poller_callback(attribute.id, (0, 0, 0))
        return
    rtt_sum = int(values[1])
    fwd_pl = int(values[2])
    bwd_pl = int(values[3])

    pobj.poller_callback(attribute.id, (
        fwd_pl / (fwd_pl + nr) * 100,
        bwd_pl / (bwd_pl + nr) * 100,
        rtt_sum / nr
    ))
