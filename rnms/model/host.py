# -*- coding: utf-8 -*-
#
# This file is part of the RoseNMS
#
# Copyright (C) 2011-2015 Craig Small <csmall@enc.com.au>
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
""" Host definition model """

import datetime
import transaction
import random
import time

from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey, Column
from sqlalchemy.types import Integer, Unicode, Boolean, String, DateTime,\
    Text, SmallInteger, BigInteger

from rnms.model import DeclarativeBase, DBSession
from rnms.model.snmp_names import SNMPEnterprise

__all__ = ['Host', 'Iface', 'ConfigBackupMethod', 'HostConfig',
           'DiscoveryHost']

MINDATE = datetime.date(1900, 1, 1)
discover_interval = 30.0  # 30 min
discover_variance = 10.0  # +- 5 minutes next discovery

SYSOBJECTID_OID = (1, 3, 6, 1, 2, 1, 1, 2, 0)


class Host(DeclarativeBase):
    __tablename__ = 'hosts'

    #{ Columns
    id = Column(Integer, autoincrement=True, primary_key=True)
    mgmt_address = Column(String(40))
    display_name = Column(String(255), nullable=False)
    zone_id = Column(Integer, ForeignKey('zones.id'))
    tftp_server = Column(String(40))
    ro_community_id = Column(Integer, ForeignKey("snmp_communities.id"))
    ro_community = relationship('SnmpCommunity',
                                foreign_keys=[ro_community_id])
    rw_community_id = Column(Integer, ForeignKey("snmp_communities.id"))
    rw_community = relationship('SnmpCommunity',
                                foreign_keys=[ro_community_id])
    trap_community_id = Column(Integer, ForeignKey("snmp_communities.id"))
    trap_community = relationship('SnmpCommunity',
                                  foreign_keys=[ro_community_id])
    autodiscovery_policy_id = Column(Integer,
                                     ForeignKey("autodiscovery_policies.id"))
    autodiscovery_policy = relationship('AutodiscoveryPolicy', backref='hosts')
    config_backup_method_id = Column(
        Integer, ForeignKey('config_backup_methods.id'), nullable=False,
        default=1)
    config_backup_method = relationship('ConfigBackupMethod')
    default_user_id = Column(Integer, ForeignKey('tg_user.user_id'))
    default_user = relationship('User')
    attributes = relationship('Attribute', backref='host',
                              cascade='all,delete,delete-orphan')
    ifaces = relationship('Iface', backref='host', order_by='Iface.id')
    configs = relationship('HostConfig', backref='host',
                           order_by='HostConfig.id',
                           cascade='all, delete, delete-orphan')
    traps = relationship('SnmpTrap', backref='host')
    show_host = Column(Boolean, default=True)
    pollable = Column(Boolean, default=True)
    created = Column(DateTime, nullable=False, default=datetime.datetime.now)
    updated = Column(DateTime, nullable=False, default=datetime.datetime.now)
    next_discover = Column(DateTime, nullable=False,
                           default=datetime.datetime.now)
    sysobjid = Column(String(250))
    #}

    def __init__(self, mgmt_address=None, display_name=None):
        if mgmt_address is not None:
            self.mgmt_address = mgmt_address
        if display_name is not None:
            self.display_name = display_name

    def __repr__(self):
        return '<Host: name={} Address={}>'.format(
            self.display_name, self.mgmt_address)

    def __unicode__(self):
        return self.display_name

    @classmethod
    def by_id(cls, hostid):
        """ Return the host whose id is hostid """
        return DBSession.query(cls).filter(cls.id == hostid).first()

    @classmethod
    def by_address(cls, address):
        """ Return the host whose management addres is ``address''."""
        return DBSession.query(cls).filter(cls.mgmt_address == address).first()

    def attrib_by_index(self, index):
        """ Return a host's attribute that has the given ''index''."""
        if self.attributes is None:
            return None
        str_index = str(index)
        for attrib in self.attributes:
            if attrib.index == str_index:
                return attrib
        return None

    def attribute_indexes(self, atype=None):
        """
        Return a list of attribute indexes for a given attribute type id
        if specified.
        """
        if self.attributes is not None:
            if atype is None:
                return [attrib.index for attrib in self.attributes]
            else:
                return [attrib.index for attrib in self.attributes
                        if attrib.attribute_type_id == atype]
        return []

    def snmp_type(self):
        """ Return a vendor,devmodel tuple of this Host's sysobjid """
        return SNMPEnterprise.oid2name(self.sysobjid)

    def main_attributes_down(self):
        """
        Return true if the attributes for the host that have poll_priority
        set are considered down
        """
        for attribute in self.attributes:
            if attribute.poll_priority and attribute.is_down():
                return True
        return False

    def ro_is_snmpv1(self):
        """ Returns True if Read Only Community is SNMP v1 """
        return self.ro_community and self.ro_community.is_snmpv1()

    def update_discover_time(self):
        """
        Update the next discover date to the next time we auto-discover
        on this host.
        """
        self.next_discover = datetime.datetime.now() + datetime.timedelta(
            seconds=(discover_interval + (random.random() - 0.5)
                     * discover_variance) * 60.0)
        transaction.commit()


class Iface(DeclarativeBase):
    __tablename__ = 'interfaces'

    #{ Columns
    id = Column(Integer, autoincrement=True, primary_key=True)
    host_id = Column(Integer, ForeignKey("hosts.id"), nullable=False)
    ifindex = Column(Integer, nullable=False)  # ifIndex
    display_name = Column(Unicode(30))  # ifDescr or idXName
    iftype = Column(Integer, nullable=False, default=1)  # other
    speed = Column(BigInteger)
    physaddr = Column(String(30))  # MAC address usually
    stacklower = Column(Integer, nullable=False, default=0)
    # ifStackLowerLayer
    ip4addr = Column(String(16))
    ip4bits = Column(SmallInteger)
    ip6addr = Column(String(40))
    ip6bits = Column(SmallInteger)
    #}

    def __init__(self, ifindex=None, display_name=None, iftype=None):
        self.host_id = 1
        self.ifindex = ifindex
        self.display_name = display_name
        self.iftype = iftype


class ConfigBackupMethod(DeclarativeBase):
    __tablename__ = 'config_backup_methods'

    #{ Columns
    id = Column(Integer, primary_key=True)
    display_name = Column(Unicode(40), nullable=False, unique=True)
    plugin_name = Column(String(40), nullable=False, unique=True)
    #}

    def __init__(self, display_name=None, plugin_name=''):
        self.display_name = display_name
        self.plugin_name = plugin_name

    @classmethod
    def default(cls):
        """ Return the type for none """
        return DBSession.query(cls).filter(
            cls.plugin_name == '').first()


class HostConfig(DeclarativeBase):
    __tablename__ = 'host_configs'

    #{ Columns
    id = Column(Integer, autoincrement=True, primary_key=True)
    created = Column(DateTime, nullable=False, default=datetime.datetime.now)
    host_id = Column(Integer, ForeignKey('hosts.id'), nullable=False)
    config = Column(Text)

    def __init__(self, host=None, config=None):
        self.host = host
        self.config = config


class DiscoveryHost(object):
    """ Host object used for autodiscovering attributes """

    def __init__(self, ad_engine, host):
        self.ad_engine = ad_engine
        self.id = host.id
        self.obj = host
        self.in_discovery = False
        self.discovery_index = -1
        self.attribute_type = None
        self.discovered_attributes = {}

    def start_discovery(self, cb_fun):
        if self.need_sysobjid():
            self.check_sysobjid(cb_fun)
            return True
        else:
            return self.cb_discovery_row(None)

    def start_discovery_row(self):
        self.in_discovery = True
        self.start_time = time.time()

    def cb_check_sysobjid(self, value):
        """ Callback for when queried host for its sysObjectID """
        if value is not None:
            new_sysobjid = value.replace('1.3.6.1.4.1', 'ent')
            self.obj.sysobjid = new_sysobjid
        self.cb_discovery_row()

    def cb_discovery_row(self, discovered_atts=None):
        """
        Finish up the current discovery and start the next one
        Return True if there is more polling going on
        """
        if self.attribute_type is not None and discovered_atts is not None:
            self.discovered_attributes[self.attribute_type.id] =\
                discovered_atts
        self.start_time = time.time()
        while True:
            self.discovery_index += 1
            self.attribute_type =\
                self.ad_engine.get_discovery_row(self.discovery_index)
            if self.attribute_type is None:
                # Got the the end of the line
                break
            if self.attribute_type.autodiscover(
                    self.ad_engine, self.obj, self.ad_engine._force):
                return True

        self.in_discovery = False
        return False

    def check_sysobjid(self, cb_fun):
        """ Check the host's system object id using SNMP """
        self.start_discovery_row()
        self.ad_engine.snmp_engine.get_str(
            self.obj, SYSOBJECTID_OID, cb_fun,
            )

    def need_sysobjid(self):
        """ Do we need to check the sysObjectId ? """
        if (self.obj.sysobjid is not None and self.obj.sysobjid != '') or\
           self.obj.ro_community.is_empty():
            return False
        return True
