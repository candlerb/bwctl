/*
 *      $Id$
 */
/************************************************************************
*									*
*			     Copyright (C)  2003			*
*				Internet2				*
*			     All Rights Reserved			*
*									*
************************************************************************/
/*
 *	File:		policy.h
 *
 *	Author:		Jeff W. Boote
 *			Internet2
 *
 *	Date:		Tue Sep 16 14:29:07 MDT 2003
 *
 *	Description:	
 *			This file declares the types needed by applications
 *			to use the "default" 
 *
 */
#ifndef	_IPF_DEFAULTS_H
#define	_IPF_DEFAULTS_H

#include <I2util/util.h>
#include <ipcntrl/ipcntrl.h>

#ifndef	IPF_KEY_FILE
#define	IPF_KEY_FILE		"iperfcd.keys"
#endif

#ifndef	IPF_LIMITS_FILE
#define	IPF_LIMITS_FILE		"iperfcd.limits"
#endif

/*
 * Holds the policy record that was parsed and contains all the "limits"
 * and identity information.
 *
 * type: (owp_policy_data*) - defined in access.h
 * location: Context Config
 */
#define IPFDPOLICY	"IPFDPOLICY"

/*
 * Holds the identifying "node" from the policy tree that contains the
 * class and limits information for the given control connection.
 *
 * type: (owp_tree_node_ptr) - defined in access.h
 * location: Control Config
 */
#define IPFDPOLICY_NODE	"IPFDPOLICY_NODE"

/*
 * Types used by policy functions
 */
#define IPFDMAXCLASSLEN	(80)

typedef struct IPFDPolicyRec IPFDPolicyRec, *IPFDPolicy;
typedef struct IPFDPolicyNodeRec IPFDPolicyNodeRec, *IPFDPolicyNode;
typedef struct IPFDPolicyKeyRec IPFDPolicyKeyRec, *IPFDPolicyKey;

struct IPFDPolicyRec{
	IPFContext		ctx;

	int			fd;	/* socket to parent. */
	char			*datadir;

	int			*retn_on_intr;	/* If one, exit I/O on sigs */

	IPFDPolicyNode		root;

	/* limits:
	 * 	key = char* (classname from "limit" lines)
	 * 	val = IPFDPolicyNode
	 */
	I2Table			limits;
	/* idents:
	 * 	key = IPFDPid
	 * 	val = IPFDPolicyNode
	 */
	I2Table			idents;
	/* keys:
	 * 	key = u_int8_t[16]	(username from ipcntrl protocol)
	 * 	val = IPFKey
	 */
	I2Table			keys;

};

typedef u_int64_t	IPFDLimitT;		/* values */
typedef u_int32_t	IPFDMesgT;

typedef struct IPFDLimRec{
	IPFDMesgT	limit;
	IPFDLimitT	value;
} IPFDLimRec;

/* parent		cname		*/
/* bandwidth		uint (bits/sec)*/
/* delete_on_fetch	on/(off)	*/
/* allow_open_mode	(on)/off	*/

#define	IPFDLimParent		0
#define	IPFDLimBandwidth	1
#define	IPFDLimPending		2
#define	IPFDLimEventHorizon	3
#define	IPFDLimDuration		4
#define	IPFDLimAllowOpenMode	5
#define	IPFDLimAllowTCP		6
#define	IPFDLimAllowUDP		7

struct IPFDPolicyNodeRec{
	IPFDPolicy		policy;
	char			*nodename;
	IPFDPolicyNode		parent;
	size_t			ilim;
	IPFDLimRec		*limits;
	IPFDLimRec		*used;
};

typedef enum{
	IPFDPidInvalid=0,
	IPFDPidDefaultType,
	IPFDPidNetmaskType,
	IPFDPidUserType
} IPFDPidType;

typedef struct{
	IPFDPidType	id_type;
	u_int8_t	mask_len;
	size_t		addrsize;
	u_int8_t	addrval[16];
} IPFDPidNetmask;

typedef struct{
	IPFDPidType	id_type;
	IPFUserID	userid;
} IPFDPidUser;

typedef union IPFDPidUnion{
	IPFDPidType	id_type;
	IPFDPidNetmask	net;
	IPFDPidUser	user;
} IPFDPidRec, *IPFDPid;

/*
 * The following section defines the message tags used to communicate
 * from the children processes to the parent to request/release
 * resources on a global basis.
 *
 * All message "type" defines will be of type IPFDMesgT.
 */
#define	IPFDMESGMARK		0xfefefefe
#define	IPFDMESGCLASS		0xcdef
#define	IPFDMESGRESOURCE	0xbeef
#define	IPFDMESGRESERVATION	0xdeadbeef
#define	IPFDMESGCOMPLETE	0xabcdefab
#define	IPFDMESGREQUEST		0xfeed
#define	IPFDMESGRELEASE		0xdead
#define	IPFDMESGCLAIM		0x1feed1

/*
 * "parent" response messages will be one of:
 */
#define IPFDMESGINVALID	0x0
#define IPFDMESGOK	0x1
#define IPFDMESGDENIED	0x2

/*
 * After forking, the new "server" process (called "child" in the following)
 * should determine the "usage class" the given connection should belong to.
 * The first message to the "parent" master process should communicate this
 * information so that all further resource requests/releases are relative
 * to that "usage class". The format of this message should be as follows:
 *
 * (All integers are in host order since this is expected to be ipc
 * communication on a single host. It could be a future enhancement to
 * allow a "single" distributed iperfcd IPCNTRL-Control server to manage
 * multiple test  endpoints at which time it might be worth the overhead
 * to deal with byte ordering issues.)
 *
 * Initial child->parent message:
 *
 * 	   0                   1                   2                   3
 * 	   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	00|                      IPFDMESGMARK                             |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	04|                      IPFDMESGCLASS                            |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	            [nul terminated ascii string of classname]
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	00|                      IPFDMESGMARK                             |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *
 * This is a child message format that is used to request or release resources.
 * (The parent should release all "temporary" resources (i.e. bandwidth)
 * on exit of the child if the child does not explicitly release the resource.
 * More "permenent" resources should only be released explicitly
 * (i.e. disk-space).
 *
 * 	   0                   1                   2                   3
 * 	   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	00|                      IPFDMESGMARK                             |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	04|                     IPFDMESGRESOURCE                          |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	08|          IPFDMESGWANT|IPFDMESGRELEASE|IPFDMESGCLAIM           |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	12|                      IPFDMesgT(limit name)                    |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	16|                        IPFDLimitT                             |
 *	20|                                                               |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	24|                      IPFDMESGMARK                             |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *
 * This is a child message format that is used to declare a test complete.
 * (The Accept Value will be 0 if the test was successful.)
 *
 * 	   0                   1                   2                   3
 * 	   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	00|                         IPFDMESGMARK                          |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	04|                       IPFDMESGCOMPLETE                        |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	08|                                                               |
 *	12|                              SID                              |
 *	16|                                                               |
 *	20|                                                               |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	24|                          Accept Value                         |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	28|                          IPFDMESGMARK                         |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *
 *
 * Parent responses to the previous two messages are of the format:
 *
 * 	   0                   1                   2                   3
 * 	   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	00|                      IPFDMESGMARK                             |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	04|                IPFDMESGOK|IPFDMESGDENIED                      |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	08|                      IPFDMESGMARK                             |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *
 * This is a child message format that is used to request reservations.
 *
 * 	   0                   1                   2                   3
 * 	   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	00|                         IPFDMESGMARK                          |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	04|                      IPFDMESGRESERVATION                      |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	08|                                                               |
 *	12|                              SID                              |
 *	16|                                                               |
 *	20|                                                               |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	24|                        Request Time                           |
 *	28|                                                               |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	32|                           Fuzz TIME                           |
 *	36|                                                               |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	40|                          Latest Time                          |
 *	44|                                                               |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	48|                            Duration                           |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	52|                           RTT TIME                            |
 *	56|                                                               |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	60|                          IPFDMESGMARK                         |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *
 * Parent responses to the reservation request are of the format:
 *
 * 	   0                   1                   2                   3
 * 	   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	00|                          IPFDMESGMARK                         |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	04|                   IPFDMESGOK|IPFDMESGDENIED                   |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	08|                        Request Time                           |
 *	12|                                                               |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	16|           Recv Port             |                             |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *	20|                          IPFDMESGMARK                         |
 *	  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 *
 *
 */

/*
 * The following api convienence functions are defined to make the child/parent
 * communication easier. (These are the functions needed by the parent in
 * the master iperfcd "resource broker" process.)
 */

extern IPFDPolicyNode
IPFDReadClass(
	IPFDPolicy	policy,
	int		fd,
	int		*retn_on_intr,
	int		*err
	);

/*
 * Returns the request type or 0.
 */
extern int
IPFDReadReqType(
		int	fd,
		int	*retn_on_intr,
		int	*err);
/*
 * returns True on success - query/lim_ret will contain request
 * err will be non-zero on error. 0 on empty read.
 */
extern IPFBoolean
IPFDReadQuery(
	int		fd,
	int		*retn_on_intr,
	IPFDMesgT	*query,
	IPFDLimRec	*lim_ret,
	int		*err
	);

extern IPFBoolean
IPFDReadReservationQuery(
	int		fd,
	int		*retn_on_intr,
	IPFSID		sid,
	IPFNum64	*req_time,
	IPFNum64	*fuzz_time,
	IPFNum64	*last_time,
	u_int32_t	*duration,
	IPFNum64	*rtt_time,
	int		*err
	);

extern IPFBoolean
IPFDReadTestComplete(
	int		fd,
	int		*retn_on_intr,
	IPFSID		sid,
	IPFAcceptType	*aval,
	int		*err
	);

extern int
IPFDSendResponse(
	int		fd,
	int		*retn_on_intr,
	IPFDMesgT	mesg
	);

extern int
IPFDSendReservationResponse(
		int		fd,
		int		*retn_on_intr,
		IPFDMesgT	mesg,
		IPFNum64	reservation,
		u_int16_t	port
		);

/*
 * This function is used to add/subtract resource allocations from the
 * current tree of resource usage. (It is also used for "fixed" value
 * resouces to determine if the request is valid or not. For "fixed"
 * value resources, the current "usage" is not tracked.)
 */
extern IPFBoolean
IPFDResourceDemand(
		IPFDPolicyNode	node,
		IPFDMesgT	query,
		IPFDLimRec	lim
		);

/*
 * This function is used to return the "fixed" limit defined for a
 * given node for a particular resource. It returns True if it was
 * able to fetch the value. (It should only return False if called
 * for a non-fixed value resource.)
 */
extern IPFBoolean
IPFDGetFixedLimit(
		IPFDPolicyNode	node,
		IPFDMesgT	limname,
		IPFDLimitT	*ret_val
		);
/*
 * Functions called directly from iperfcd regarding "policy" decisions
 * (If false, check err_ret to determine if it is an "error" condition,
 * or if open_mode is simply denied.)
 */
extern IPFBoolean
IPFDAllowOpenMode(
	IPFDPolicy	policy,
	struct sockaddr	*peer_addr,
	IPFErrSeverity	*err_ret
	);

/*
 * Functions actually used to install policy hooks into libipcntrl.
 */
extern IPFBoolean
IPFDGetAESKey(
	IPFContext	ctx,
	const IPFUserID	userid,
	u_int8_t	*key_ret,
	IPFErrSeverity	*err_ret
	);

extern IPFBoolean
IPFDCheckControlPolicy(
	IPFControl	cntrl,
	IPFSessionMode	mode,
	const IPFUserID	userid,
	struct sockaddr	*local_saddr,
	struct sockaddr	*remote_saddr,
	IPFErrSeverity	*err_ret
	);

extern IPFBoolean
IPFDCheckTestPolicy(
	IPFControl	cntrl,
	IPFSID		sid,
	IPFBoolean	local_sender,
	struct sockaddr	*local_saddr,
	struct sockaddr	*remote_saddr,
	socklen_t	sa_len,
	IPFTestSpec	*tspec,
	IPFNum64	fuzz_time,
	IPFNum64	*reservation_ret,
	u_int16_t	*port_ret,
	void		**closure,
	IPFErrSeverity	*err_ret
	);

extern void
IPFDTestComplete(
	IPFControl	cntrl,
	void		*closure,
	IPFAcceptType	aval
	);

extern IPFDPolicy
IPFDPolicyInstall(
	IPFContext	ctx,
	char		*datadir,	/* root dir for datafiles	*/
	char		*confdir,	/* conf dir for policy		*/
	char		*iperfcmd,	/* iperf exec path		*/
	int		*retn_on_intr,
	char		**lbuf,
	size_t		*lbuf_max
	);

#endif	/*	_IPF_DEFAULTS_H	*/
