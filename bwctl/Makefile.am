#
#      $Id$
#
#########################################################################
#									#
#			   Copyright (C)  2003				#
#	     			Internet2				#
#			   All Rights Reserved				#
#									#
#########################################################################
#
#	File:		Makefile.am
#
#	Author:		Jeff Boote
#			Internet2
#
#	Date:		Fri Sep 12 13:33:27 MDT 2003
#
#	Description:

bin_PROGRAMS	= bwctl
bwctl_SOURCES	= bwctl.c bwctlP.h
bwctl_CFLAGS	= -I..

if TOOL_THRULAY
if USE_SYS_THRULAY
BWLIBTHRULAY = -lthrulay
else
BWLIBTHRULAY = ../thrulay/thrulay/libthrulay.la
endif
else
BWLIBTHRULAY =
endif

bwctl_LDADD	= -L../bwlib -lbwlib $(BWLIBTHRULAY) -lI2util
bwctl_LINKS     = bwtraceroute$(exeext) bwping$(exeext)

bwtraceroute$(exeext): bwctl$(exeext)
	@if test -f $@; then $(RM) $@; fi; \
	$(LN_S) bwctl $@;

bwping$(exeext): bwctl$(exeext)
	@if test -f $@; then $(RM) $@; fi; \
	$(LN_S) bwctl $@;

all-local: $(bwctl_LINKS)

CLEANFILES   = $(bwctl_LINKS)

#
# Someday perhaps this will be generated by automake...
#
install-exec-hook:
	@cd $(DESTDIR)$(bindir) && \
	if test -f bwctl; then \
	   for l in $(bwctl_LINKS); do \
	      if test -f $$l; then $(RM) $$l; fi; \
	      echo "$(LN_S) $(DESTDIR)$(bindir)/bwctl $(DESTDIR)$(bindir)/$$l"; \
	      $(LN_S) bwctl $$l; \
	   done; \
	fi

# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# 
