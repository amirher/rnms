
Introduction
============
RoseNMS (rnms) is, as the name implies, a Network Management System.
What this means is rnms is a piece of software that gathers information
on devices out on a network and tries to meaningfully interpret them to 
make monitoring and managment simpler.

rnms is written in python and is based upon the Turbogears 2 web framework.
The basic concept is largely built around the ideas that were put into
another NMS program called JFFNMS.

For more updates, please visit the `RoseNMS website`_

History of RoseNMS
========================
Rnms is the third network management system that I have worked on. In the early
2000's there was a design which was not much more than some penciled scribbles
for something along the lines of logcheck. That program was called GEMS
(Generic Event Management System) and didn't progress past the concept stage.

What accelerated GEMS' demise was a project called Just For Fun Network
Management System or JFFNMS_.  This program was written in PHP and combined
the status polling of Nagios with the RRD graphs of cricket and MRTG.  As it
was written in PHP this had all the bonuses and problems of other PHP programs.
It was able to reasonably easily run on Windows and Linux systems, amongst 
others and handled the database and SNMP parts through modules.

Maintaining a PHP program is not easy and tracking down bugs gets very 
difficult.  There needed to be a better way and one solution was to keep
PHP but use a framework such as CakePHP_. While this solved some of the framework
problems, it still left PHP with all its quirkyness.

Another series of searches and it was decided to start a completely new
project.  Given it was a rewrite, then there was no need to stay with the same
langauge.  Also the web framework needed to be something reasonably substancial
that took care of things such as database handling, authentication and
web request routing.  After some research and false starts, in October 2011, RoseNMS was born based upon TurboGears_.

.. _RoseNMS website: http://rnms.org/
.. _JFFNMS: http://jffnms.org/
.. _CakePHP: http://cakephp.org/
.. _TurboGears: http://turbogears.org/
