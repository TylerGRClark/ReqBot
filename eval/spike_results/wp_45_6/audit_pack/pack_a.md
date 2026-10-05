# Extraction-model comparison, pass A only: source text only

Read RUBRIC.md first (it is the WP-45.1(b) rubric, unchanged). Label pass A only; there is no pass B and no stem in this pack. Cards are in random order and carry no model name.

## R001
Document: NIST.SP.800-125  |  chunk 40  |  page 15

Quote (the requirement text to judge):
> Most importantly, virtualizing multiple servers on the same host tends to negatively affect security because of the logical proximity of the servers and the potential impact of a single compromise affecting all the servers on a host.

Chunk 40 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[2. Introduction to Full Virtualization > 2.4 Full Virtualization Use Cases > 2.4.1 Server Virtualization]

Virtualizing a server can provide some security benefits. Running a server within a hypervisor provides a sandbox, which can limit the impact of a compromise, and the hypervisor might provide a smaller attack surface than a host operating system would, reducing the possibility of expanding a successful compromise outside the guest OS. However, server virtualization does not prevent attackers from compromising the server through vulnerabilities in the server application or the guest OS, nor does it prevent attackers from directly compromising the host OS (if present), such as attacking the host OS's network services from another host on the same subnet. ⟦Most importantly, virtualizing multiple servers on the same host tends to negatively affect security because of the logical proximity of the servers and the potential impact of a single compromise affecting all the servers on a host.⟧
The discussions below address common reasons for using single server and multiple server virtualization.
1 The specification for OVF version is published by the Distributed Management Task Force, Inc. (DMTF).
~~~~

Previous chunk 39:
~~~~text
[2. Introduction to Full Virtualization > 2.4 Full Virtualization Use Cases]

Full virtualization solutions have two major use cases: server virtualization and desktop virtualization. These are described below.
~~~~

## R002
Document: afman17-2101  |  chunk 30  |  page 11

Quote (the requirement text to judge):
> Provide Title 10 responsibilities of power, physical security, floor space, and onsite support coordination for the base DISN network Point of Present.

Chunk 30 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[ROLES AND RESPONSIBILITIES > 2.5. AF Installations will:]

2.5.1.  Ensure AF main operating bases (MOBs) have a DISN presence as stated in CJCSI 6211.02  and  provide  requisite  site  support  (known  as  Title  10  responsibilities)  for  DISN equipment located on bases, posts, camps, and stations.
2.5.1.1.  ⟦Provide  Title  10  responsibilities  of  power,  physical  security,  floor  space,  and onsite support coordination for the base DISN network Point of Present.⟧
2.5.1.2.  Provide  Base  Operations  Support  to  DISN  LHC infrastructure  installed  on  the base. The AF Installation may delegate appointed responsibilities to the base Communications Squadron/Flight. The main authority/delegated authority:
2.5.1.2.1.  Appoint  a  DISN  Node  Site  Coordinator    (NSC)    and    alternate  in accordance with DISAC 310-55- 9 paragraph C2.1.2, for base level support of the DISN  on  AF  installations  where  DISN  equipment  resides.  The  appointment  letter must be updated and resubmitted when any of its content changes and verified at least annually.
~~~~

Previous chunk 29:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.4. Major Commands, Management Headquarters (MHQ), AF level Organizations will:]

2.4.5.  Ensure all subordinate organization(s) contractor DISN SBU IP DATA and SECRET IP  DATA  connection(s)  align  with  all  guidance  in  the  DISA  DISN  Connection  Process Guide (CPG).
- 2.4.6.  Ensure  AF  Management  HQ's  and  subordinate  organization(s)  whose  transport requirements exceed  existing available DISN  capabilities are funded  to cover those requirements for up to two years until AF corporate adjusts Program Objective Memorandum (POM) submission.
- 2.4.7.  Work with non-AF tenants to coordinate cost impact of LHC requirements that exceed available DISN infrastructure.
2.4.8.  Validate, approve and transmit AF Top Secret/Sensitive Compartmented Information (TS/SCI) TS/SCI IP DATA and NSANet requirements and network connections
~~~~

## R003
Document: NIST.SP.800-125  |  chunk 68  |  page 22

Quote (the requirement text to judge):
> If remote administration is enabled in a hypervisor, access to all remote administration interfaces should be restricted by a firewall.

Chunk 68 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4. Security Recommendations for Virtualization Components > 4.1 Hypervisor Security]

Hypervisors can be managed in different ways, with some hypervisors allowing management through multiple methods. It is important to secure each hypervisor management interface, both locally and remotely accessible. The capability for remote administration can usually be enabled or disabled in the virtualization management system. ⟦If remote administration is enabled in a hypervisor, access to all remote administration interfaces should be restricted by a firewall.⟧ Also, hypervisor management communications should be protected. One option is to have a dedicated management network that is separate from all other networks and that can only be accessed by authorized administrators. Management communications carried on untrusted networks must be encrypted using FIPS-approved methods, provided by either the virtualization solution or a third-party solution, such as a virtual private network (VPN) that encapsulates the management traffic.
~~~~

Previous chunk 67:
~~~~text
[4. Security Recommendations for Virtualization Components > 4.1 Hypervisor Security]

The programs that control the hypervisor should be secured using methods similar to those used to protect other software running on desktops and servers. The security of the entire virtual infrastructure relies on the security of the virtualization management system that controls the hypervisor and allows the operator to start guest OSs, create new guest OS images, and perform other actions. Because of the security implications of these actions, access to the virtualization management system should be restricted to authorized administrators only. Some virtualization management systems allow different level of access to different users, such as giving some users read-only access to the administrative interface of a guest OS, other users control over particular guest OSs, and yet other users complete administrative control. Most hypervisor software currently only uses passwords for access control; this may be too weak for some organizations' security policies and may require the use of compensating controls, such as a separate authentication system used for restricting access to the host on which the virtualization management system is installed.
~~~~

## R004
Document: DODI 8410.03  |  chunk 11  |  page 8

Quote (the requirement text to judge):
> Create, manage, and maintain a common repository based upon security classifications within the MDR for all data-exchange schemas and SNMP MIBs used by NM systems, including supporting documentation and interface characteristics and specifications.

Chunk 11 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- g.  ⟦Create, manage, and maintain a common repository based upon security classifications within the MDR for all data-exchange schemas and SNMP MIBs used by NM systems, including supporting documentation and interface characteristics and specifications.⟧
- h.  Participate in applicable standards bodies and organizations to advocate for and aid in developing standards, protocols, and mechanisms for translating NM information from current formats (e.g., SNMP) to ones that facilitate net-centric information sharing (e.g., extensible markup language).
- i.  Develop, in coordination with the DoD Components, a GIG technical profile (GTP) to define the interface specifications for exchanging data between NM systems.
~~~~

Previous chunk 10:
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- b.  Develop and maintain, with support from the DoD Components, the definition of NM data exchanges, translations, and associated data schemas among all NM systems, to include tactical edge NM systems.  This effort shall leverage and employ industry and commercial data standards, architectures, models, and exchange mechanisms to the maximum extent possible.
- c.  Define common data standards for sharing information and data between NM and SM systems IAW DoDI 8320.05 (Reference (n)).
- d.  Establish and maintain a standard dictionary for use in constructing standard NM data schemas for exchanging NM information between NM systems and for exposing NM data to non-NM systems.
- e.  Establish naming conventions and standards that facilitate the sharing of NM information and control capabilities among NM systems across established NetOps operational hierarchies and NM domains.
- f.  Establish and maintain definitions and interface control documents for standard mechanisms for exchanging NM information between NM systems and for exposing data to nonNM systems.
~~~~

## R005
Document: DODI 8410.03  |  chunk 36  |  page 19

Quote (the requirement text to judge):
> Management information obtained from NEs shall be classified, stored, processed, and shared IAW the USSTRATCOM GIG NetOps Security Classification Guide and other applicable classification guides.

Chunk 36 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[5.  NM SECURITY]

- a.  Data exchanges between NM systems shall be encrypted per DISA Security Technical Implementation Guides Network Infrastructure (Reference (ab)) and shall be processed and protected at the appropriate classification level.
- b.  Management information obtained from NEs shall be classified, stored, processed, and shared IAW the USSTRATCOM GIG NetOps Security Classification Guide (Reference (ac)) and other applicable classification guides.  NM data that provides sensitive operational status of the network or the status of the network's ability to support real-world operations shall be protected as sensitive information (minimum) or at an appropriate higher classification level based on the classification of the network it is derived from.
~~~~

Previous chunk 35:
~~~~text
[4.  SLAs]

- (4)  Mean time to repair failures in network equipment or connectivity.
- (5)  Throughput of a given network node, by traffic type.
- (6)  Percentage of available bandwidth consumed on a given link, by traffic type.
- (7)  Fault status, by node priority.
- (8)  Packet error rate and bit error rate (average and standard deviation) through a given network node.
- (9)  Quality of service requirements for NM and control plane traffic.
~~~~

## R006
Document: DODI 8410.03  |  chunk 24  |  page 14

Quote (the requirement text to judge):
> program offices shall work with DISA to identify and vet program specific data standards, schemas, and exchange mechanisms prior to them being submitted to CDRUSSTRATCOM for approval.

Chunk 24 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[2.  NM DATA EXCHANGE GUIDELINES]

- b.  The CDRUSSTRATCOM, IAW Reference (c) and functioning IAW Reference (g), shall vet and approve NM data schemas and sharing mechanisms.
- c.  DoD programs of record (POR) shall adopt and implement NM data schemas and netcentric sharing mechanisms that have been approved by CDRUSSTRATCOM.  In situations where it is determined that adopting approved NM data schemas and net-centric sharing mechanisms would result in unacceptable delay or increased costs to a POR, a request for waiver will be submitted via the applicable acquisition oversight process.
- (1)  Where standards or data schemas are not available or have not been approved, ⟦program offices shall work with DISA to identify and vet program specific data standards, schemas, and exchange mechanisms prior to them being submitted to CDRUSSTRATCOM for approval.⟧
- (2)  Requests for approval of data schema or sharing mechanism submitted to USSTRATCOM must be reviewed and adjudicated within 90 days of their submittal to ensure that program development timelines should not be adversely impacted.
~~~~

Previous chunk 23:
~~~~text
[2.  NM DATA EXCHANGE GUIDELINES]

- a.  The DoD shall adopt and implement the TeleManagement (TM) Forum Information Framework (formerly known as the Shared Information and Data Model) and the Desktop Management Task Force (DMTF), Common Information Model (CIM) as the foundation NM information and data models and the National Institute of Standards and Technology (NIST) Security Content Automation Protocol as the baseline protocol and standards for sharing security management information sharing (References (u), (v), and (w)).  Drawing on the DISR, other industry-standard information and data models (e.g., Internet Engineering Task Force (IETF), DMTF CIM, IETF SMIv2) and protocols (e.g., International Telecommunications UnionTelecommunication Cybersecurity Information Exchange (ITU-T CYBEX)) may be used to tailor those baselines where application requirements and other circumstances so warrant.  Only if existing standards cannot be extended shall DoD Components adopt and implement nonstandards based data schemas and exchange mechanisms.
~~~~

## R007
Document: NIST.SP.800-125  |  chunk 73  |  page 24

Quote (the requirement text to judge):
> someone who can reboot the host computer that the hypervisor is running on could alter some of the security settings for the hypervisor

Chunk 73 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4. Security Recommendations for Virtualization Components > 4.1 Hypervisor Security]

Of course, it is also important to provide physical access controls for the hardware on which the virtualization system runs. For example, hosted hypervisors are typically controlled by management software that can be used by anyone with access to the keyboard and mouse. Even bare metal hypervisors require physical security: ⟦someone who can reboot the host computer that the hypervisor is running on could alter some of the security settings for the hypervisor⟧. It is also important to secure the external resources that the hypervisor uses, particularly data on hard drives and other storage devices.
~~~~

Previous chunk 72:
~~~~text
[4. Security Recommendations for Virtualization Components > 4.1 Hypervisor Security]

-  Consider using introspection capabilities to monitor the security of each guest OS. If a guest OS is compromised, its security controls may be disabled or reconfigured so as to suppress any signs of compromise. Having security services in the hypervisor permits security monitoring even when the guest OS is compromised.
-  Consider using introspection capabilities to monitor the security of activity occurring between guest OSs. This is particularly important for communications that in a non-virtualized environment were carried over networks and monitored by network security controls (such as network firewalls, security appliances, and network IDPS sensors).
-  Carefully monitor the hypervisor itself for signs of compromise. This includes using self-integrity monitoring capabilities that hypervisors may provide, as well as monitoring and analyzing hypervisor logs on an ongoing basis.
~~~~

## R008
Document: NIST.SP.800-125  |  chunk 50  |  page 18

Quote (the requirement text to judge):
> In physical partitioning, the hypervisor assigns separate physical resources to each guest OS, such as disk partitions, disk drives, and network interface cards.

Chunk 50 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[3. Virtualization Security Overview > 3.1 Guest OS Isolation]

Resources may be partitioned physically or logically. In physical partitioning , the hypervisor assigns separate physical resources to each guest OS, such as disk partitions, disk drives, and network interface cards. Logical partitioning may divide resources on a single host or across multiple hosts as in a pool of resources with the same security impact level categorization, allowing multiple guest OSs to share the same physical resources, such as processors and RAM, with the hypervisor mediating access to the resources. Physical partitioning sets hard limits on resources for each guest OS because unused capacity from one resource may not be accessed by any other guest OS. However, having physical separation for resources may provide stronger security and improved performance than logical partitioning. Many virtualization systems can do both physical and logical partitioning. Some organizations have policies about which application data can physically reside on drives with the data of other applications, and such policies should take into account physical and logical partitioning in hypervisors.
~~~~

Previous chunk 49:
~~~~text
[3. Virtualization Security Overview > 3.1 Guest OS Isolation]

The hypervisor is responsible for managing guest OS access to hardware (e.g., CPU, memory, storage). The hypervisor partitions these resources so that each guest OS can access its own resources but cannot encroach on the other guest OSs' resources or any resources not allocated for virtualization use. This prevents unauthorized access to resources and also helps prevent one guest OS from injecting malware into another, such as infecting a guest OS's files or placing malware code into another guest OS's memory. Separately, partitioning can also reduce the threat of denial of service conditions caused by excess resource consumption in other guest OSs on the same hypervisor.
~~~~

## R009
Document: NIST.SP.800-125  |  chunk 81  |  page 26

Quote (the requirement text to judge):
> an organization might have a network security policy that says that all network switches connecting multiple servers must be managed and that traffic between the servers be monitored for suspicious activity.

Chunk 81 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4. Security Recommendations for Virtualization Components > 4.3 Virtualized Infrastructure Security]

Hypervisor systems that connect multiple guest OSs together on a virtual network present issues for organizations whose policies require that all networks be monitored in specified fashions. For example, ⟦an organization might have a network security policy that says that all network switches connecting multiple servers must be managed and that traffic between the servers be monitored for suspicious activity.⟧ However, network switches in most virtual systems do not have such a capability.  Some virtual switches support virtual LAN (VLAN) and firewall capabilites to provide separation and isolation of the VM network traffic.  In some environments, additional security appliances can be implemted to inspect, control, shape, and monitor the VM network communications in a centralized location.
Hypervisors sometimes offer virtual storage networks and virtual interfaces to existing hardware storage networks. These features offer the same security problems as virtual networks, namely that organizations whose security policies require monitoring those connections cannot use the same methods for virtual storage as they do for physical storage. Using physical interfaces to existing networked storage can eliminate this problem, but also reduces some of the flexibility that hypervisors offer.
~~~~

Previous chunk 80:
~~~~text
[4. Security Recommendations for Virtualization Components > 4.3 Virtualized Infrastructure Security]

Virtualization provides simulation of hardware such as storage and network interfaces. This infrastructure is as important to the security of a virtualized guest OS as real hardware infrastructure is to an operating system running on a physical computer. Many virtualization systems have features to provide access control to the virtual hardware, particularly storage and networking. Access to virtual hardware should be strictly limited to the guest OSs that will use it. For example, if a virtual hard drive will be shared between two guest OSs, only those two OSs should have access to the virtual hard drive. Some virtual hardware is meant to be widely shared. For example, a disk image that represents an installation CD may
be shared among many guest OSs; still, access to that image should be read-only, and no guest image should have write access to it.
~~~~

## R010
Document: DODI 8410.03  |  chunk 28  |  page 16

Quote (the requirement text to judge):
> All MIBs along with full descriptions of their use and format shall be stored in an MIB registry managed and published by DISA.

Chunk 28 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[3.  NM USE OF SNMP]

- a.  All SNMP MIBs used in the DoD shall comply with technical standards in the DISR and DISA Security Technical Implementation Guides (STIGs).
- b.  ⟦All MIBs along with full descriptions of their use and format shall be stored in an MIB registry managed and published by DISA.⟧
- c.  Where possible, elements in multiple MIBs that refer to the same parameter shall be formatted and identified the same way.  Standard formats and identifications shall be maintained in a DoD-published MIB data format and dictionary established and maintained by DISA.
- d.  New SNMP managed resources and management applications shall use the latest approved version of SNMP, to take advantage of the additional security features provided with this version of the protocol.  Existing systems that use SNMP shall transition to the latest approved SNMP version when feasible.
- e.  The latest version of SNMP shall be implemented with a security model appropriate to the security of the network rather than the default model.
- f.  Existing systems that use SNMP v1 or v2c shall implement the following security precautions in the period prior to transition to the latest approved version of SNMP:
~~~~

Previous chunk 27:
~~~~text
[2.  NM DATA EXCHANGE GUIDELINES]

- i.  The CDRUSSTRATCOM, in coordination with DISA and the DoD Components, shall define a minimum set of standards and values for reporting  information based on International Telegraph and Telephone Consultative Committee (CCITT) Recommendation X.731 (Reference (y)) and other applicable IETF, Distributed Management Task Force, and TM Forum standards.
~~~~

## R011
Document: afman17-2101  |  chunk 33  |  page 12

Quote (the requirement text to judge):
> All Air Force Centers, Agencies, and Other Key Stakeholder will Validate centrally funded SBU IP DATA and SECRET IP DATA transport connections, and Internet Protocol addressing, on-site assistance requests and systems configuration.

Chunk 33 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[ROLES AND RESPONSIBILITIES > 2.7. All Air Force Centers, Agencies, and Other Key Stakeholder will:]

2.7.1.  Validate  centrally  funded  SBU  IP  DATA  and  SECRET  IP  DATA  transport connections,  and  Internet  Protocol  addressing,  on-site  assistance  requests  and  systems configuration. This responsibility includes conducting Review & Revalidation on connections every 2 years.
- 2.7.1.1.  Submit requests to terminate unused AF funded SBU IP DATA and SECRET IP DATA connections when no longer required.
- 2.7.2.  Program Management Offices:
- 2.7.2.1.  Ensure  networked systems that use  LHC transport are bandwidth-efficient and include implementation of software and/or hardware compression/acceleration technologies where possible.
- 2.7.2.2.  Determine system LHC bandwidth requirements by base/site and submit circuit bandwidth requirements according to the AF LHC Requirements Process.
- 2.7.2.3.  Review/revalidate bandwidth requirements prior to initial fielding.
- 2.7.2.4.  Program  for  DISN  LHC  costs  as  part  of  overall  lifecycle  costs  and  Program Objective Memorandum.
~~~~

Previous chunk 32:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.6. All AF Organizations that own/fund DISN LHC circuits/services must:]

2.6.1.  Appoint  an  Authorized  Funding  Official  (AFO)  in  writing  to  their  management headquarters  Lead  Authorized  Funding  Official  (LAFO).  The  AFO  is  the  unit  level individual responsible for managing LHC funding/paying for circuits and services.
- 2.6.2.  Execute AFO duties as detailed in Chapter 2, paragraph 2.10 of this AFMAN.
- 2.6.3.  Submit requests to terminate unused AF funded circuits or services when no longer required.
~~~~

## R012
Document: DODI 8410.03  |  chunk 38  |  page 20

Quote (the requirement text to judge):
> The DoD Components with DISA support shall jointly establish NM standards for tactical edge NEs.

Chunk 38 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[5.  NM SECURITY]

6.  NM STANDARDS AND SCHEMAS FOR TACTICAL EDGE NE.  To support end-to-end SA and NM system reporting criteria, common NM standards are required to support spectrumdependent systems and tactical edge NEs.
- a.  In consideration of tactical edge NM requirements, the DoD Components with DISA support shall jointly establish NM standards for tactical edge NEs.  The standards shall be maintained by DISA and incorporated into the baseline schemas for NM.  These standards shall consider the unique properties of tactical networking, including but not limited to:
- (1)  The ad-hoc nature of such networks.
- (2)  The requirement for NEs to connect and disconnect at random due to mobility-related constraints.
- (3)  The often limited bandwidth available.
- (4)  Operational requirements to remain in a non-transmitting state for extended periods of time.
- b.  As requested, DISA shall support program managers, in the incorporation of these standards into new or existing programs of record.
~~~~

Previous chunk 37:
~~~~text
[5.  NM SECURITY]

- c.  NM system operator and supervisory positions (e.g., system administrators, network managers and controllers, router and switch administrators, managers and controllers) performing NM IA functions as defined in DoD 8570.01-M (Reference (ad)) shall be designated IA Technical Category Level 2 and IA Management Category Level 2 positions and as critical sensitive positions as defined by DoD 5200.2-R (Reference (ae)), and military, government civilian, and contractor personnel filling them shall meet all required background checks, training, and certification requirements prior to assuming their duties.
- d.  Access to NM systems shall be authorized by the appropriate unit level commander responsible for the NM system.  Only those users with proper credentials and access authorizations will be granted access to NM systems.  NM system users shall comply with the applicable cybersecurity training and certification requirements IAW Reference (ad).
- e.  NM functions are critical within the network infrastructure.  Accordingly, supply chain risk management shall be applied to the acquisition of NM functionality IAW DoDI 5200.44 (Reference (af)) and DoDI 5200.39 (Reference (ag)).
~~~~

## R013
Document: DODI 8410.03  |  chunk 20  |  page 12

Quote (the requirement text to judge):
> Establish and issue priorities for the collection and sharing of NM data.

Chunk 20 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4.  DIRECTOR, OPERATIONAL TEST AND EVALUATION (DOT&E).  The DOT&E shall:]

- k.  Provide the NM and SM data necessary to fulfill the commander's critical information requirements in support of established DoD cyberspace operational hierarchies.
- l.  Ensure, in coordination with DISA, all DoD equipment containing or potentially containing personally identifiable information and other data of a sensitive nature is managed in accordance with DoDI 5000.64 (Reference (s)).
10.  CJCS.  The CJCS, in addition to the responsibilities in section 8 of this enclosure and in coordination with the other Heads of the DoD Components, shall:
- a.  ⟦Establish and issue priorities for the collection and sharing of NM data.⟧
- b.  Develop and promulgate joint NM tactics, techniques, and procedures.
- c.  In coordination with the Combatant Commanders, establish requirements for sharing NM information and data with coalition partner networks.
11.  COMMANDERS OF THE COMBATANT COMMANDS.  The Commanders of the Combatant Commands, in addition to the responsibilities in section 8 of this enclosure, shall support the Joint Staff in establishing requirements for sharing NM information and data with coalition partner networks.
~~~~

Previous chunk 19:
~~~~text
[4.  DIRECTOR, OPERATIONAL TEST AND EVALUATION (DOT&E).  The DOT&E shall:]

- (2)  Where appropriate, these standards shall be established jointly, maintained by DISA, and incorporated into the baseline schemas for NM.
~~~~

## R014
Document: NIST.SP.800-125  |  chunk 40  |  page 15

Quote (the requirement text to judge):
> Running a server within a hypervisor provides a sandbox, which can limit the impact of a compromise, and the hypervisor might provide a smaller attack surface than a host operating system would, reducing the possibility of expanding a successful compromise outside the guest OS.

Chunk 40 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[2. Introduction to Full Virtualization > 2.4 Full Virtualization Use Cases > 2.4.1 Server Virtualization]

Virtualizing a server can provide some security benefits. ⟦Running a server within a hypervisor provides a sandbox, which can limit the impact of a compromise, and the hypervisor might provide a smaller attack surface than a host operating system would, reducing the possibility of expanding a successful compromise outside the guest OS.⟧ However, server virtualization does not prevent attackers from compromising the server through vulnerabilities in the server application or the guest OS, nor does it prevent attackers from directly compromising the host OS (if present), such as attacking the host OS's network services from another host on the same subnet. Most importantly, virtualizing multiple servers on the same host tends to negatively affect security because of the logical proximity of the servers and the potential impact of a single compromise affecting all the servers on a host.
The discussions below address common reasons for using single server and multiple server virtualization.
1 The specification for OVF version is published by the Distributed Management Task Force, Inc. (DMTF).
~~~~

Previous chunk 39:
~~~~text
[2. Introduction to Full Virtualization > 2.4 Full Virtualization Use Cases]

Full virtualization solutions have two major use cases: server virtualization and desktop virtualization. These are described below.
~~~~

## R015
Document: DODI 8410.03  |  chunk 33  |  page 18

Quote (the requirement text to judge):
> Allowable NM system initialization time and data sync (or data re-sync due to NM and radio reconnection).

Chunk 33 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4.  SLAs]

- (b)  Required NM data update rates.
- (c)  Maximum allowable time from when an event takes place to when it is reported by the NM system, as well as the location of event.
- (d)  Location of the NM event.
- (e)  ⟦Allowable NM system initialization time and data sync (or data re-sync due to NM and radio reconnection).⟧
- (f)  Required local event storage requirements (if any).
- (g)  Reporting formats, destinations, and update rates (if finished reports are to be provided.
- (h)  Mechanisms for enforcement, auditing, and assurance.
- (6)  A description of NM system backup, recovery and continuity of operations requirement.
- (7)  Procedures for changing and terminating the SLA.
- (8)  A description of the remedies available to the customer in the event the NM system does not perform as agreed.
~~~~

Previous chunk 32:
~~~~text
[4.  SLAs]

- (5)  How NM service levels will be monitored and reported.  This section must include: where, how, and in what format NM information and data will be collected; how often it will be collected; how it will be shared with the customer; how often it will be shared with the customer; how NM information and data will be archived; and duration archived information will be retained IAW Reference (h).  This section will define for all parties:
8. (a)  The characteristics of the NM information to be exchanged (e.g., data schema(s) used, specialized data formatting (if any), and any non-standard characteristics).
~~~~

## R016
Document: afman17-2101  |  chunk 46  |  page 15

Quote (the requirement text to judge):
> Approve role requests to an AFOs assigned funding PDC's.

Chunk 46 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[ROLES AND RESPONSIBILITIES > 2.11. Lead Authorized Funding Official (LAFO) are located at: > 2.11.1.2.  The LAFO responsibilities are to:]

- 2.11.1.2.1.  Ensure unit's under their purview reconcile their monthly LHC invoices for  telecommunications  equipment  and  service  inventories,  CSA's,  and/or  other acquisition documents before authorizing payment.
2.11.1.2.2.  Ensure units obtain access to Networx/Enterprise Infrastructure Solutions (EIS) vendor on-line systems for commercial long distance usage and billing data by contacting the AF EIS Program Administrator at AF LHC Flight, 38 CYRS/SCC.
2.11.1.2.3.  Approve role requests under their command within two business days of receiving role request notification. (T-3)
2.11.1.2.4.  ⟦Approve role requests to an AFOs assigned funding PDC's.⟧
Note: Only AF level LHC personnel have access to all AF PDC's. A LAFO may approve an ABO role requests with (%) TIBI access to multiple funding codes.
~~~~

Previous chunk 45:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.11. Lead Authorized Funding Official (LAFO) are located at:]

- 2.11.1.  Headquarter level organization who fund and own DISN LHC circuits/services must appoint a Headquarters level primary and alternate LAFO in writing to AF LHC Flight, 38 CYRS/SCC Circuit Management Office.
- 2.11.1.1.  A  LAFO is a civilian or military personnel who is responsible for approving and  managing  LHC  funding  for  DISN  circuits  and  services.  The  LAFO  provides management oversight  to  their  units  AFO  and  the  Authorized  Billing  Officials  (ABO) along with process guidance in regard to management of DISN LHC funding.
~~~~

## R017
Document: DODI 8410.03  |  chunk 37  |  page 19

Quote (the requirement text to judge):
> NM system users shall comply with the applicable cybersecurity training and certification requirements IAW Reference (ad).

Chunk 37 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[5.  NM SECURITY]

- c.  NM system operator and supervisory positions (e.g., system administrators, network managers and controllers, router and switch administrators, managers and controllers) performing NM IA functions as defined in DoD 8570.01-M (Reference (ad)) shall be designated IA Technical Category Level 2 and IA Management Category Level 2 positions and as critical sensitive positions as defined by DoD 5200.2-R (Reference (ae)), and military, government civilian, and contractor personnel filling them shall meet all required background checks, training, and certification requirements prior to assuming their duties.
- d.  Access to NM systems shall be authorized by the appropriate unit level commander responsible for the NM system.  Only those users with proper credentials and access authorizations will be granted access to NM systems.  ⟦NM system users shall comply with the applicable cybersecurity training and certification requirements IAW Reference (ad).⟧
- e.  NM functions are critical within the network infrastructure.  Accordingly, supply chain risk management shall be applied to the acquisition of NM functionality IAW DoDI 5200.44 (Reference (af)) and DoDI 5200.39 (Reference (ag)).
~~~~

Previous chunk 36:
~~~~text
[5.  NM SECURITY]

- a.  Data exchanges between NM systems shall be encrypted per DISA Security Technical Implementation Guides Network Infrastructure (Reference (ab)) and shall be processed and protected at the appropriate classification level.
- b.  Management information obtained from NEs shall be classified, stored, processed, and shared IAW the USSTRATCOM GIG NetOps Security Classification Guide (Reference (ac)) and other applicable classification guides.  NM data that provides sensitive operational status of the network or the status of the network's ability to support real-world operations shall be protected as sensitive information (minimum) or at an appropriate higher classification level based on the classification of the network it is derived from.
~~~~

## R018
Document: NIST.SP.800-125  |  chunk 9  |  page 6

Quote (the requirement text to judge):
> The same is true for applications running on guest OSs: if the organization has a security policy for an application, it should apply the same regardless of whether the application is running on an OS within a hypervisor or on an OS running on hardware.

Chunk 9 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[Secure all elements of a full virtualization solution and maintain their security.]

The security of a full virtualization solution is heavily dependent on the individual security of each of its components, from the hypervisor and host OS (if applicable) to guest OSs, applications, and storage. Organizations should secure all of these elements and maintain their security based on sound security practices, such as keeping software up-to-date with security patches, using secure configuration baselines, and using host-based firewalls, antivirus software, or other appropriate mechanisms to detect and stop attacks. In general, organizations should have the same security controls in place for virtualized operating systems as they have for the same operating systems running directly on hardware. ⟦The same is true for
applications running on guest OSs: if the organization has a security policy for an application, it should apply the same regardless of whether the application is running on an OS within a hypervisor or on an OS running on hardware.⟧
~~~~

Previous chunk 8:
~~~~text
[Executive Summary]

Full virtualization has some negative security implications. Virtualization adds layers of technology, which can increase the security management burden by necessitating additional security controls. Also, combining many systems onto a single physical computer can cause a larger impact if a security compromise occurs. Further, some virtualization systems make it easy to share information between the systems; this convenience can turn out to be an attack vector if it is not carefully controlled. In some cases, virtualized environments are quite dynamic, which makes creating and maintaining the necessary security boundaries more complex.
This publication discusses the security concerns associated with full virtualization technologies for server and desktop virtualization, and provides recommendations for addressing these concerns. Most existing recommended security practices remain applicable in virtual environments. The practices described in this document build on and assume the implementation of practices described in other NIST publications.
To improve the security of server and desktop full virtualization technologies, organizations should implement the following recommendations:
~~~~

## R019
Document: DODI 8410.03  |  chunk 6  |  page 7

Quote (the requirement text to judge):
> Develop Mission-driven NM metrics for tactical and non-tactical networks and NM systems that enable consistent assessments of DoD network protection and performance.

Chunk 6 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- a.  Provide strategy, policy, oversight, and guidance for NM capability, planning, definition, and implementation across the DoD Information Enterprise and GIG IAW Reference (b).
- b.  In coordination with Under Secretary of Defense for Acquisition, Technology, and Logistics (USD(AT&L)) and the Heads of the DoD Components, develop:
- (1)  End-to-end NM architectures and strategies that support efficient, effective, and secure NM operations in tactical and non-tactical networks and improve interoperability across NM systems.
- (2)  Mission-driven NM metrics for tactical and non-tactical networks and NM systems that enable consistent assessments of DoD network protection and performance.
- (3)  Strategies and architectures for IT resource management capabilities that efficiently and effectively integrate NM and SM systems across doctrine, organization, training, materiel, leadership and education, personnel and facilities (DOTMLPF).
~~~~

Previous chunk 5:
~~~~text
[Enclosures]

1.  References
2.  Responsibilities
3.  Procedures
Glossary
~~~~

## R020
Document: DODI 8410.03  |  chunk 16  |  page 10

Quote (the requirement text to judge):
> The DOT&E shall support DoD CIO, USD(AT&L), Director, DISA, and Commander, USSTRATCOM (CDRUSSTRATCOM) in developing mission-driven metrics and end-to-end NM architectures and strategies that support efficient NM operations in tactical and non-tactical networks to improve interoperability and integration across NM systems.

Chunk 16 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[4.  DIRECTOR, OPERATIONAL TEST AND EVALUATION (DOT&E).  The DOT&E shall:]

- b.  Support DoD CIO, USD(AT&L), Director, DISA, and Commander, USSTRATCOM (CDRUSSTRATCOM) in developing mission-driven metrics and end-to-end NM architectures
and strategies that support efficient NM operations in tactical and non-tactical networks to improve interoperability and integration across NM systems.
~~~~

Previous chunk 15:
~~~~text
[4.  DIRECTOR, OPERATIONAL TEST AND EVALUATION (DOT&E).  The DOT&E shall:]

7.  DIRECTOR, NATIONAL SECURITY AGENCY (DIRNSA)/CHIEF, CENTRAL SECURITY SERVICE (CHCSS).  The DIRNSA/CHCSS, under the authority, direction, and control of the USD(I), in addition to the responsibilities in sections 8 and 9 of this enclosure, and, consistent with the National Manager responsibilities assigned to DIRNSA by National Security Directive 42 (Reference (q)), shall lead, with the support of the other DoD Components, the development of suitable technical standards; administrative guidance; key-management protocols, devices, and systems; encryption methods; and other items as required to enable NM systems and the NE they manage to comply with applicable security controls.
8. HEADS OF THE DEFENSE INTELLIGENCE COMPONENTS.  The Heads of the Defense Intelligence Components shall execute their NM responsibilities consistent with Intelligence Community Directive 502 (Reference (r)).
9.  HEADS OF THE DoD COMPONENTS.  The Heads of the DoD Components shall:
- a.  Execute NM within the portions of the Defense Information Enterprise within their assigned area of responsibility (AOR) IAW Reference (b) and in support of Combatant Commanders' responsibilities.
~~~~

## R021
Document: afman17-2101  |  chunk 45  |  page 15

Quote (the requirement text to judge):
> A LAFO is a civilian or military personnel who is responsible for approving and managing LHC funding for DISN circuits and services.

Chunk 45 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[ROLES AND RESPONSIBILITIES > 2.11. Lead Authorized Funding Official (LAFO) are located at:]

- 2.11.1.  Headquarter level organization who fund and own DISN LHC circuits/services must appoint a Headquarters level primary and alternate LAFO in writing to AF LHC Flight, 38 CYRS/SCC Circuit Management Office.
- 2.11.1.1.  ⟦A  LAFO is a civilian or military personnel who is responsible for approving and  managing  LHC  funding  for  DISN  circuits  and  services.⟧  The  LAFO  provides management oversight  to  their  units  AFO  and  the  Authorized  Billing  Officials  (ABO) along with process guidance in regard to management of DISN LHC funding.
~~~~

Previous chunk 44:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.10. Authorized Funding Official (AFO) for organizations who fund and own DISN AF LHC circuits and/or services must: > 2.10.1.1.  AFO's will:]

- 2.10.1.1.1.  Update at the start of each fiscal  year the funding PDC with a certified MORD number, Line of Accounting (LOA), and Customer Account Information in TIBI  (T-0)
- 2.10.1.1.2.  Approve and/or disapprove DISA StoreFront Service Requests.
- 2.10.1.1.3.  Reconcile LHC  invoices  for all  DISN  ordered  telecommunications equipment and services, CSA's and/or other acquisition documents before authorizing payment. (T-0)
- 2.10.1.1.4.  Submit  PDC  requests  to  38  CYRS/SCC  Financial  Analyst  point  of contact.
- 2.10.1.1.5.  Validate  OSD/DITCO  Quarterly  Statistical  Sampling  invoice  in  TIBI when requested by 38 CYRS/SCC Financial Analyst. (T-0)
~~~~

## R022
Document: afman17-2101  |  chunk 34  |  page 12

Quote (the requirement text to judge):
> All CMO's will: Prepare, review, validate, approve, and/or reject Service Requests in DISA StoreFront for long-haul circuits, services, and equipment submitted by subordinate organizations.

Chunk 34 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.1.  MAJCOM level CMO workload responsibilities were consolidated under the AF LHC Flight at 38 CYRS/SCC.
- 2.8.2.  All  CMO  not  part  of  the  MAJCOM  CMO's  consolidation  effort  retain  their  CMO responsibilities to:
- 2.8.2.1.  Provision,  track,  and  manage  LHC  circuits  and  service  throughout  their  life cycle.
- 2.8.2.2.  Register and obtain appropriate role assignments in DISA StoreFront provisioning tool and AF TCOSS for their respective organizations.  All CMO's will:
- 2.8.2.2.1.  Prepare, review, validate, approve, and/or reject Service Requests in DISA StoreFront for long-haul circuits, services, and equipment submitted by subordinate organizations.
- 2.8.2.2.2.  Assist  and  guide  subordinate  organizations  on  LHC  management  which include  (but  not  limited  to  user  account  registration  in  DISA  StoreFront  and  AF TCOSS required to manage LHC circuits, services and funding.
~~~~

Previous chunk 33:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.7. All Air Force Centers, Agencies, and Other Key Stakeholder will:]

2.7.1.  Validate  centrally  funded  SBU  IP  DATA  and  SECRET  IP  DATA  transport connections,  and  Internet  Protocol  addressing,  on-site  assistance  requests  and  systems configuration. This responsibility includes conducting Review & Revalidation on connections every 2 years.
- 2.7.1.1.  Submit requests to terminate unused AF funded SBU IP DATA and SECRET IP DATA connections when no longer required.
- 2.7.2.  Program Management Offices:
- 2.7.2.1.  Ensure  networked systems that use  LHC transport are bandwidth-efficient and include implementation of software and/or hardware compression/acceleration technologies where possible.
- 2.7.2.2.  Determine system LHC bandwidth requirements by base/site and submit circuit bandwidth requirements according to the AF LHC Requirements Process.
- 2.7.2.3.  Review/revalidate bandwidth requirements prior to initial fielding.
- 2.7.2.4.  Program  for  DISN  LHC  costs  as  part  of  overall  lifecycle  costs  and  Program Objective Memorandum.
~~~~

## R023
Document: DODI 8410.03  |  chunk 10  |  page 8

Quote (the requirement text to judge):
> The DoD CIO, shall develop and maintain, with support from the DoD Components, the definition of NM data exchanges, translations, and associated data schemas among all NM systems, to include tactical edge NM systems.

Chunk 10 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- b.  Develop and maintain, with support from the DoD Components, the definition of NM data exchanges, translations, and associated data schemas among all NM systems, to include tactical edge NM systems.  This effort shall leverage and employ industry and commercial data standards, architectures, models, and exchange mechanisms to the maximum extent possible.
- c.  Define common data standards for sharing information and data between NM and SM systems IAW DoDI 8320.05 (Reference (n)).
- d.  Establish and maintain a standard dictionary for use in constructing standard NM data schemas for exchanging NM information between NM systems and for exposing NM data to non-NM systems.
- e.  Establish naming conventions and standards that facilitate the sharing of NM information and control capabilities among NM systems across established NetOps operational hierarchies and NM domains.
- f.  Establish and maintain definitions and interface control documents for standard mechanisms for exchanging NM information between NM systems and for exposing data to nonNM systems.
~~~~

Previous chunk 9:
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- h.  Develop, in coordination with the Heads of the DoD Components, architectures and standards for automated CM and PBNM capabilities based on the results of the USD(AT&L) assigned responsibilities contained in this Instruction.
2.  DIRECTOR, DISA.  The Director, DISA, under the authority, direction, and control of the DoD CIO, and in addition to the responsibilities in sections 8 and 9 of this enclosure and IAW DoDD 5105.19 (Reference (l)), and in coordination with the Heads of DoD Components, shall:
- a.  Establish and maintain repositories of NM data schemas, technical standards and specifications, interface definitions, and SNMP management information bases (MIBs) based upon security classifications, to include proprietary SNMP MIBs IAW the Internet Engineering Task Force Request For Comment 2578, 'Structure of Management Information Version 2 (SMIv2)' (Reference (m)).
~~~~

## R024
Document: DODI 8410.03  |  chunk 13  |  page 9

Quote (the requirement text to judge):
> The USD(AT&L) shall implement automated CM and PBNM capabilities and standards in new or modified NM systems, including but not specifically limited to determining architectures and technical approaches for: Determining standard methods for human override of automated configuration changes.

Chunk 13 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[3.  USD(AT&L).  The USD(AT&L) shall:]

- a.  Provide coordination and support to ensure that any policies, guidance, or requirements proposed by the DoD CIO regarding SM and NM requirements impacting access to defense networks and vendor facing applications by members of the Defense Industrial Base (DIB) will not place any undue burdens on industry.
- b.  Prepare and coordinate acquisition and contracting policy, procedures, and regulation among DIB members and Federal partners necessary to implement this Instruction.
- c.  Coordinate with DIB members supplying  materiel and services, to ensure an executable and affordable migration strategy to meet SM and NM requirements resulting from the implementation of  this Instruction.
- d.  Implement automated CM and PBNM capabilities and standards in new or modified NM systems, including but not specifically limited to determining architectures and technical approaches for:
- (1)  Network traffic bandwidth prioritization.
- (2)  Contingency-based configuration changes that will satisfy a typical joint operation, including potential coalition partners or similar.
- (3)  Implementing automated configuration change technologies.
- (4)  Determining standard methods for human override of automated configuration changes.
~~~~

Previous chunk 12:
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- j.  Develop and promulgate DoD-wide standards and guidelines for use of NM protocols (such as SNMP or network configuration protocol) for communication of NM information between NM systems and their managed network elements (NEs).
- k.  Develop, in coordination with the Commander, U.S. Strategic Command (USSTRATCOM), technical guidance for integrating and correlating NM and SM capabilities to enable near real-time end-to-end network SA throughout the GIG.
- l.  Support the USD(AT&L) in reviewing and studying automated CM and PBNM capabilities and standards.
- m.  Develop and promulgate technical guidance and architectures for developing and implementing automated CM and PBNM systems.
- n.  Establish and maintain a central repository of SLAs.
~~~~

## R025
Document: NIST.SP.800-125  |  chunk 72  |  page 23

Quote (the requirement text to judge):
> Consider using introspection capabilities to monitor the security of activity occurring between guest OSs.

Chunk 72 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4. Security Recommendations for Virtualization Components > 4.1 Hypervisor Security]

-  Consider using introspection capabilities to monitor the security of each guest OS. If a guest OS is compromised, its security controls may be disabled or reconfigured so as to suppress any signs of compromise. Having security services in the hypervisor permits security monitoring even when the guest OS is compromised.
-  ⟦Consider using introspection capabilities to monitor the security of activity occurring between guest OSs.⟧ This is particularly important for communications that in a non-virtualized environment were carried over networks and monitored by network security controls (such as network firewalls, security appliances, and network IDPS sensors).
-  Carefully monitor the hypervisor itself for signs of compromise. This includes using self-integrity monitoring capabilities that hypervisors may provide, as well as monitoring and analyzing hypervisor logs on an ongoing basis.
~~~~

Previous chunk 71:
~~~~text
[4. Security Recommendations for Virtualization Components > 4.1 Hypervisor Security]

-  Install all updates to the hypervisor as they are released by the vendor. Most hypervisors have features that will check for updates automatically and install the updates when found. Centralized patch management solutions can also be used to administer updates.
-  Restrict administrative access to the management interfaces of the hypervisor.  Protect all management communication channels using a dedicated management network or the management network communications is authenticated and encrypted using FIPS 140-2 validated cryptographic modules.
-  Synchronize the virtualized infrastructure to a trusted authoritative time server.
-  Disconnect unused physical hardware from the host system. For example, a removable disk drive might be occasionally used for backups, but it should be disconnected when not actively being used for backup or restores. Disconnect unused NICs from any network.
-  Disable all hypervisor services such as clipboard- or file-sharing between the guest OS and the host OS unless they are needed. Each of these services can provide a possible attack vector. File sharing can also be an attack vector on systems where more than one guest OS share the same folder with the host OS.
~~~~

## R026
Document: DODI 8410.03  |  chunk 33  |  page 18

Quote (the requirement text to judge):
> Required local event storage requirements (if any).

Chunk 33 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4.  SLAs]

- (b)  Required NM data update rates.
- (c)  Maximum allowable time from when an event takes place to when it is reported by the NM system, as well as the location of event.
- (d)  Location of the NM event.
- (e)  Allowable NM system initialization time and data sync (or data re-sync due to NM and radio reconnection).
- (f)  ⟦Required local event storage requirements (if any).⟧
- (g)  Reporting formats, destinations, and update rates (if finished reports are to be provided.
- (h)  Mechanisms for enforcement, auditing, and assurance.
- (6)  A description of NM system backup, recovery and continuity of operations requirement.
- (7)  Procedures for changing and terminating the SLA.
- (8)  A description of the remedies available to the customer in the event the NM system does not perform as agreed.
~~~~

Previous chunk 32:
~~~~text
[4.  SLAs]

- (5)  How NM service levels will be monitored and reported.  This section must include: where, how, and in what format NM information and data will be collected; how often it will be collected; how it will be shared with the customer; how often it will be shared with the customer; how NM information and data will be archived; and duration archived information will be retained IAW Reference (h).  This section will define for all parties:
8. (a)  The characteristics of the NM information to be exchanged (e.g., data schema(s) used, specialized data formatting (if any), and any non-standard characteristics).
~~~~

## R027
Document: afman17-2101  |  chunk 44  |  page 15

Quote (the requirement text to judge):
> Validate OSD/DITCO Quarterly Statistical Sampling invoice in TIBI when requested by 38 CYRS/SCC Financial Analyst. (T-0)

Chunk 44 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[ROLES AND RESPONSIBILITIES > 2.10. Authorized Funding Official (AFO) for organizations who fund and own DISN AF LHC circuits and/or services must: > 2.10.1.1.  AFO's will:]

- 2.10.1.1.1.  Update at the start of each fiscal  year the funding PDC with a certified MORD number, Line of Accounting (LOA), and Customer Account Information in TIBI  (T-0)
- 2.10.1.1.2.  Approve and/or disapprove DISA StoreFront Service Requests.
- 2.10.1.1.3.  Reconcile LHC  invoices  for all  DISN  ordered  telecommunications equipment and services, CSA's and/or other acquisition documents before authorizing payment. (T-0)
- 2.10.1.1.4.  Submit  PDC  requests  to  38  CYRS/SCC  Financial  Analyst  point  of contact.
- 2.10.1.1.5.  ⟦Validate  OSD/DITCO  Quarterly  Statistical  Sampling  invoice  in  TIBI when requested by 38 CYRS/SCC Financial Analyst. (T-0)⟧
~~~~

Previous chunk 43:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.10. Authorized Funding Official (AFO) for organizations who fund and own DISN AF LHC circuits and/or services must:]

- 2.10.1.  Appoint an AFO in writing to their Headquarters level LAFO. An AFO is a civilian or military personnel at unit level responsible for approving and managing LHC funding for circuits and services. AFOs can only request access to their assigned PDC's.
~~~~

## R028
Document: afman17-2101  |  chunk 44  |  page 15

Quote (the requirement text to judge):
> AFO's will reconcile LHC invoices for all DISN ordered telecommunications equipment and services, CSA's and/or other acquisition documents before authorizing payment

Chunk 44 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[ROLES AND RESPONSIBILITIES > 2.10. Authorized Funding Official (AFO) for organizations who fund and own DISN AF LHC circuits and/or services must: > 2.10.1.1.  AFO's will:]

- 2.10.1.1.1.  Update at the start of each fiscal  year the funding PDC with a certified MORD number, Line of Accounting (LOA), and Customer Account Information in TIBI  (T-0)
- 2.10.1.1.2.  Approve and/or disapprove DISA StoreFront Service Requests.
- 2.10.1.1.3.  Reconcile LHC  invoices  for all  DISN  ordered  telecommunications equipment and services, CSA's and/or other acquisition documents before authorizing payment. (T-0)
- 2.10.1.1.4.  Submit  PDC  requests  to  38  CYRS/SCC  Financial  Analyst  point  of contact.
- 2.10.1.1.5.  Validate  OSD/DITCO  Quarterly  Statistical  Sampling  invoice  in  TIBI when requested by 38 CYRS/SCC Financial Analyst. (T-0)
~~~~

Previous chunk 43:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.10. Authorized Funding Official (AFO) for organizations who fund and own DISN AF LHC circuits and/or services must:]

- 2.10.1.  Appoint an AFO in writing to their Headquarters level LAFO. An AFO is a civilian or military personnel at unit level responsible for approving and managing LHC funding for circuits and services. AFOs can only request access to their assigned PDC's.
~~~~

## R029
Document: NIST.SP.800-125  |  chunk 86  |  page 27

Quote (the requirement text to judge):
> Organizations that manage guest OSs for multiple users should also be particularly careful that any changes made by one user do not propagate back to the main image and then appear in the images used by other users.

Chunk 86 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4. Security Recommendations for Virtualization Components > 4.4 Desktop Virtualization Security]

Another benefit of using managed guest OS images is that they can be updated by the organization as needed without requiring user intervention. However, image distribution can be problematic because a single guest OS image can be many gigabytes in size, making it difficult to download. Organizations may choose to lessen the frequency of full image updates by configuring images to patch and update their operating systems and applications automatically. ⟦Organizations that manage guest OSs for multiple users should also be particularly careful that any changes made by one user do not propagate back to the main image and then appear in the images used by other users.⟧
~~~~

Previous chunk 85:
~~~~text
[4. Security Recommendations for Virtualization Components > 4.4 Desktop Virtualization Security]

Organizations typically take advantage of these types of desktop virtualization solutions to reduce the security concerns associated with connecting unmanaged systems to internal resources, as well as to lessen dependence on distributing managed computers to individuals and trying to ensure that unmanaged computers meet security requirements. An often overlooked concern about checking personally owned computers is that scans and other checks may affect privacy. For the data and resources the guest OS accesses, it can provide some protection from threats in the host OS-for example, by establishing a VPN to the organization and by encrypting stored data. However, it cannot fully protect against threats in the host OS unless the host OS is bypassed altogether (e.g., by booting the computer to run a hypervisor from removable media).
~~~~

## R030
Document: afman17-2101  |  chunk 39  |  page 14

Quote (the requirement text to judge):
> All other ASI's are coordinated directly with DISA and guidance in DISAC 310-55-1, Status Reporting.

Chunk 39 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.3.7.  Review and revalidate all requirements for base telecommunications equipment and services. (T-0)
- 2.8.3.7.1.  Terminate services that are uneconomical or no longer needed in accordance with CJCSI 6211.02. (T-0)
- 2.8.3.8.  Coordinate  Authorized  Service  Interruptions  (ASIs)  with  Subordinate  units, affected AF customers and tenant organizations. Submit concurrence or non- concurrence to the base Communications Focal Point for SBU I DATA,  SECRET IP DATA, and 24 AF designated mission  critical circuits.  ⟦All other ASI's are coordinated directly with DISA and guidance in DISAC 310-55-1, Status Reporting.⟧ (T-3)
- 2.8.3.9.  Coordinate and schedule power outages (i.e. base Civil Engineering) with DISA, Major Commands,  Cyber  Operations  Flight/690   Network    Support  Squadron,    and affected  AF  customers  that  will   impact   communication facilities, rooms, racks, and equipment.
~~~~

Previous chunk 38:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.3.3.3.  Circuit Layout Records which is a drawing that depicts the physical layout of trunks and circuits.
- 2.8.3.3.4.  Master Station Log which is a record of information on significant events occurring within the area of assigned responsibility.
- 2.8.3.4.  Track facility, link, trunk, circuit, channel, equipment outages, and HAZCONs within the activity area of responsibility. Outage and restoration records are maintained in accordance with DISAC 310-70-1 and DISAC 310-55-1.
- 2.8.3.5.  Establish a trend analysis program on all circuits, trunks for which they are the Circuit Control Office (CCO) or servicing activity, and on all circuits and trunks which terminate at their station in accordance with DISAC 310-70-1 and DISAC 310-130-2.
- 2.8.3.6.  Maintain an inventory of all base telecommunications equipment and services in accordance with CJCSI 6211.02. (T-0)
~~~~

## R031
Document: DODI 8410.03  |  chunk 36  |  page 19

Quote (the requirement text to judge):
> Data exchanges between NM systems shall be encrypted per DISA Security Technical Implementation Guides Network Infrastructure and shall be processed and protected at the appropriate classification level.

Chunk 36 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[5.  NM SECURITY]

- a.  Data exchanges between NM systems shall be encrypted per DISA Security Technical Implementation Guides Network Infrastructure (Reference (ab)) and shall be processed and protected at the appropriate classification level.
- b.  Management information obtained from NEs shall be classified, stored, processed, and shared IAW the USSTRATCOM GIG NetOps Security Classification Guide (Reference (ac)) and other applicable classification guides.  NM data that provides sensitive operational status of the network or the status of the network's ability to support real-world operations shall be protected as sensitive information (minimum) or at an appropriate higher classification level based on the classification of the network it is derived from.
~~~~

Previous chunk 35:
~~~~text
[4.  SLAs]

- (4)  Mean time to repair failures in network equipment or connectivity.
- (5)  Throughput of a given network node, by traffic type.
- (6)  Percentage of available bandwidth consumed on a given link, by traffic type.
- (7)  Fault status, by node priority.
- (8)  Packet error rate and bit error rate (average and standard deviation) through a given network node.
- (9)  Quality of service requirements for NM and control plane traffic.
~~~~

## R032
Document: DODI 8410.03  |  chunk 3  |  page 2

Quote (the requirement text to judge):
> DoD Components operating NM systems shall develop service level agreements (SLAs) or similar agreements to ensure quality of service, interoperability, and availability of NM data exchanged between NM systems and with any authorized user IAW section 4 of Enclosure 3.

Chunk 3 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[2.  APPLICABILITY.  This Instruction:]

- c.  ⟦DoD Components operating NM systems shall develop service level agreements (SLAs) or similar agreements to ensure quality of service, interoperability, and availability of NM data exchanged between NM systems and with any authorized user IAW section 4 of Enclosure 3.⟧
- d.  NM systems shall incorporate mechanisms or processes that ensure resiliency and continuity of operations in the event of a failure, loss, or disruption of NM capabilities due to a cyber attack or other manmade or natural occurrence.
- e.  NM systems shall have and use integrated automated CM and PBNM capabilities to improve DoD's ability to rapidly and consistently respond to cybersecurity events and maintain network availability and performance.
- f.  NM and SM systems shall be integrated, as appropriate, to create information technology (IT) resource management capabilities that provide the warfighter with enhanced situational awareness (SA) to support common understanding, planning, and monitoring; distributed network and spectrum control; and reduce life cycle costs.
- g.  NM interfaces to DoD mission partners (e.g., coalition and industrial suppliers) shall leverage and employ industry and commercial data standards, architectures, models, and exchange mechanisms to the maximum extent possible.
~~~~

Previous chunk 2:
~~~~text
[2.  APPLICABILITY.  This Instruction:]

- c.  Shall not alter or supersede the existing authorities and policies of the Director of National Intelligence regarding the protection of sensitive compartmented information (SCI) and special access programs (SAP) for intelligence as directed by Executive Order 12333 (Reference (e)) and other laws and regulations.  The application of the provisions and procedures of this Instruction to SCI or other SAP for intelligence information systems is encouraged where they may complement or discuss areas not otherwise specifically addressed.
3.  DEFINITIONS.  See Glossary.
4.  POLICY.  It is DoD policy that:
- a.  All NM systems shall be capable of distributed network control and facilitate net-centric sharing of network configuration, status, security, performance, utilization, and mission impact data with authorized users in accordance with (IAW) section 2 of Enclosure 3 of this Instruction.
- b.  Systems that use Simple Network Management Protocol (SNMP) shall use the latest version as the target protocol version IAW section 3 of Enclosure 3.
~~~~

## R033
Document: afman17-2101  |  chunk 36  |  page 13

Quote (the requirement text to judge):
> TCFs identified as Facility Control Offices or Intermediate Facility Control Offices should follow DISAC 310-70-1 DISA PAC Supplement 1 guidance.

Chunk 36 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.2.7.1.  Ensure DOD CIO endorsed DISA/DITCO policy is followed which states zero  tolerance  for  expired  CSAs.  DISA/DITCO  intent  is  to  issue  vendors  a  nonrevocable termination letter within two weeks of CSA expiration date.
- 2.8.3.  Technical  Control  Facility  (TCF),  Patch  and  Test  Facility  (PTF),  and/or  Circuit Actions.
- 2.8.3.1.  Responsible for base LHC management in accordance with all DOD Directives and Instructions, DISA Circulars (DISACs), DISA Notices, and AF policies.
- 2.8.3.1.1.  Technical  Control  Facilities  and  Patch  and  Test  Facilities  in  the  Pacific area  should  follow  the  Pacific  area  guidance  in  DISAC  310-70-1  DISA  PAC Supplement 1 and DISA PAC C 310-70-58 along with other DISA PAC circulars as they apply.
- 2.8.3.1.2.  ⟦TCFs identified as Facility Control Offices or Intermediate Facility Control Offices should follow DISAC 310-70-1 DISA PAC Supplement 1 guidance.⟧
~~~~

Previous chunk 35:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.2.2.3.  Prepare orders in accordance with DISAC 310-130-1 and DISA Provisioning Notices.
- 2.8.2.3.  Identify  and  obtain  special  circuit  considerations  (i.e.  diversity,  avoidance, redundancy, and survivability) to meet mission specifications.
- 2.8.2.4.  Identify proper TSP level (DISAC 310-130-4 and DISAC 310-130-1).
- 2.8.2.5.  Ensure  TS/SCI  connections  (TS/SCI  IP  DATA,  NSANet)  are  submitted  for validation and approval to the appropriate A2 designated office.
- 2.8.2.6.  Ensure  all  Defense  Service  Network  (DSN)  dedicated  precedence  service requests are approved in accordance with CJCSI 6211.02.
- 2.8.2.7.  Manage  expired/expiring  CSA    program  to  ensure  commercial  circuits  and services  are  re-awarded  or  discontinued  in  accordance  with  DISA    Global  Contract Reaward Actions.
~~~~

## R034
Document: afman17-2101  |  chunk 44  |  page 15

Quote (the requirement text to judge):
> AFO's will validate OSD/DITCO Quarterly Statistical Sampling invoice in TIBI when requested by 38 CYRS/SCC Financial Analyst

Chunk 44 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[ROLES AND RESPONSIBILITIES > 2.10. Authorized Funding Official (AFO) for organizations who fund and own DISN AF LHC circuits and/or services must: > 2.10.1.1.  AFO's will:]

- 2.10.1.1.1.  Update at the start of each fiscal  year the funding PDC with a certified MORD number, Line of Accounting (LOA), and Customer Account Information in TIBI  (T-0)
- 2.10.1.1.2.  Approve and/or disapprove DISA StoreFront Service Requests.
- 2.10.1.1.3.  Reconcile LHC  invoices  for all  DISN  ordered  telecommunications equipment and services, CSA's and/or other acquisition documents before authorizing payment. (T-0)
- 2.10.1.1.4.  Submit  PDC  requests  to  38  CYRS/SCC  Financial  Analyst  point  of contact.
- 2.10.1.1.5.  Validate  OSD/DITCO  Quarterly  Statistical  Sampling  invoice  in  TIBI when requested by 38 CYRS/SCC Financial Analyst. (T-0)
~~~~

Previous chunk 43:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.10. Authorized Funding Official (AFO) for organizations who fund and own DISN AF LHC circuits and/or services must:]

- 2.10.1.  Appoint an AFO in writing to their Headquarters level LAFO. An AFO is a civilian or military personnel at unit level responsible for approving and managing LHC funding for circuits and services. AFOs can only request access to their assigned PDC's.
~~~~

## R035
Document: DODI 8410.03  |  chunk 33  |  page 18

Quote (the requirement text to judge):
> Procedures for changing and terminating the SLA.

Chunk 33 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4.  SLAs]

- (b)  Required NM data update rates.
- (c)  Maximum allowable time from when an event takes place to when it is reported by the NM system, as well as the location of event.
- (d)  Location of the NM event.
- (e)  Allowable NM system initialization time and data sync (or data re-sync due to NM and radio reconnection).
- (f)  Required local event storage requirements (if any).
- (g)  Reporting formats, destinations, and update rates (if finished reports are to be provided.
- (h)  Mechanisms for enforcement, auditing, and assurance.
- (6)  A description of NM system backup, recovery and continuity of operations requirement.
- (7)  ⟦Procedures for changing and terminating the SLA.⟧
- (8)  A description of the remedies available to the customer in the event the NM system does not perform as agreed.
~~~~

Previous chunk 32:
~~~~text
[4.  SLAs]

- (5)  How NM service levels will be monitored and reported.  This section must include: where, how, and in what format NM information and data will be collected; how often it will be collected; how it will be shared with the customer; how often it will be shared with the customer; how NM information and data will be archived; and duration archived information will be retained IAW Reference (h).  This section will define for all parties:
8. (a)  The characteristics of the NM information to be exchanged (e.g., data schema(s) used, specialized data formatting (if any), and any non-standard characteristics).
~~~~

## R036
Document: DODI 8410.03  |  chunk 13  |  page 9

Quote (the requirement text to judge):
> The USD(AT&L) shall implement automated CM and PBNM capabilities and standards in new or modified NM systems, including but not specifically limited to determining architectures and technical approaches for: Implementing automated configuration change technologies.

Chunk 13 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[3.  USD(AT&L).  The USD(AT&L) shall:]

- a.  Provide coordination and support to ensure that any policies, guidance, or requirements proposed by the DoD CIO regarding SM and NM requirements impacting access to defense networks and vendor facing applications by members of the Defense Industrial Base (DIB) will not place any undue burdens on industry.
- b.  Prepare and coordinate acquisition and contracting policy, procedures, and regulation among DIB members and Federal partners necessary to implement this Instruction.
- c.  Coordinate with DIB members supplying  materiel and services, to ensure an executable and affordable migration strategy to meet SM and NM requirements resulting from the implementation of  this Instruction.
- d.  Implement automated CM and PBNM capabilities and standards in new or modified NM systems, including but not specifically limited to determining architectures and technical approaches for:
- (1)  Network traffic bandwidth prioritization.
- (2)  Contingency-based configuration changes that will satisfy a typical joint operation, including potential coalition partners or similar.
- (3)  Implementing automated configuration change technologies.
- (4)  Determining standard methods for human override of automated configuration changes.
~~~~

Previous chunk 12:
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- j.  Develop and promulgate DoD-wide standards and guidelines for use of NM protocols (such as SNMP or network configuration protocol) for communication of NM information between NM systems and their managed network elements (NEs).
- k.  Develop, in coordination with the Commander, U.S. Strategic Command (USSTRATCOM), technical guidance for integrating and correlating NM and SM capabilities to enable near real-time end-to-end network SA throughout the GIG.
- l.  Support the USD(AT&L) in reviewing and studying automated CM and PBNM capabilities and standards.
- m.  Develop and promulgate technical guidance and architectures for developing and implementing automated CM and PBNM systems.
- n.  Establish and maintain a central repository of SLAs.
~~~~

## R037
Document: afman17-2101  |  chunk 48  |  page 17

Quote (the requirement text to judge):
> CISPs will not be used to host classified systems directly, a CISP connect can only be used to tunnel the classified connection.

Chunk 48 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[COMMERCIAL INTERNET SERVICE PROVIDER (ISP) > 3.1. Commercial Internet Service Provider (CISP) Connection]

3.1.1.  Types. CISP connections do not connect to the AF Information Network infrastructure and  require  authorization  through  the  DoD  and  AF  DISN  waiver  process.  Information Services  (ISs)  that  process,  store  and  transmit  DoD  data  using  a  CISP  connection  must perform categorization in accordance with DoDI 8510.01 tailored appropriately to determine the  set  of  security  controls  to  be  implemented  with  the  approval  of  the  IS's  Authorizing Official (AO).  Tailoring of security controls must take into account the sensitivity of the data being  processed,  stored,  and  transmitted  (e.g.,  controlled  DoD  data,  publically  releasable data) and protection of the supporting IS. The CISP connection cannot be connected directly to the DISN. Use of an approved hardware/software secure tunnel (IPSEC only) such as an AF-  approved,  virtual  private  network  (VPN)  across  a  CISP  circuit  to  connect  to  the DISN/AF  Information  Network  (AFIN)  is  allowed.  Tunneling  classified  data  via  a  CISP requires a DODIN waiver based in DoD Policy. These systems shall not be connected to the base network/NIPRNET with the privileges of '.mil' registered users. ⟦CISPs will not be used to host classified systems directly, a CISP connect can only be used to tunnel the classified connection.⟧
~~~~

Previous chunk 47:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.11. Lead Authorized Funding Official (LAFO) are located at: > 2.11.1.2.  The LAFO responsibilities are to:]

2.11.1.2.5.  Ensure  all  AFO  contact  information  is  up-to-date  for  primary  and alternate  AFOs  in  TIBI  database  for  local  funded  program  codes  under  their Headquarters. (T-3)
2.11.1.2.6.  Submit  locally  funded  PDC  worksheet  to  AF  LHC  Flight  Financial Managers.
2.11.1.2.7.  Provide training to AFO's under their area of responsibility.
~~~~

## R038
Document: NIST.SP.800-125  |  chunk 74  |  page 24

Quote (the requirement text to judge):
> There should be tight access controls to the host OS to prevent someone from gaining access through the host OS to the virtualization system and possibly changing its settings or modifying the guest OSs.

Chunk 74 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[4. Security Recommendations for Virtualization Components > 4.1 Hypervisor Security]

There are additional recommendations for hosted virtualization solutions for server virtualization. Hosted virtualization exposes the system to more threats because of the presence of a host OS. To increase the security of the host OS, minimize the number of applications other than the hypervisor that are ever run on the system. All unneeded applications should be removed. Those that remain should be restricted as much as possible to prevent malware from being inadvertently installed on the system. For example, a web browser is often used to download updates to the hypervisor, and also to read instructions and bulletins about the hypervisor. If the computer is intended to be exclusively used to run the hosted hypervisor, the web browser should have as many settings as possible adjusted to their highest security level.
Because hosted virtualization systems are run under host OSs, the security of every guest OS relies on the security of the host OS. This means that there should be tight access controls to the host OS to prevent someone from gaining access through the host OS to the virtualization system and possibly changing its settings or modifying the guest OSs.
~~~~

Previous chunk 73:
~~~~text
[4. Security Recommendations for Virtualization Components > 4.1 Hypervisor Security]

Of course, it is also important to provide physical access controls for the hardware on which the virtualization system runs. For example, hosted hypervisors are typically controlled by management software that can be used by anyone with access to the keyboard and mouse. Even bare metal hypervisors require physical security: someone who can reboot the host computer that the hypervisor is running on could alter some of the security settings for the hypervisor. It is also important to secure the external resources that the hypervisor uses, particularly data on hard drives and other storage devices.
~~~~

## R039
Document: DODI 8410.03  |  chunk 30  |  page 17

Quote (the requirement text to judge):
> Device, account, and application passwords will not be passed over SNMP until the transition to the latest version is accomplished.

Chunk 30 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[3.  NM USE OF SNMP]

- (7)  The community strings shall be modified from default settings - default 'public' and 'private' strings shall not be utilized.
- (8)  Periodic SNMP polling should be done with a read-only community string, and readwrite strings should be used only for write operations, based on the capabilities of the NM system.
- (9)  Unauthorized attempts to access SNMP managed NE shall be aggressively monitored and reported.
- (10)  ⟦Device, account, and application passwords will not be passed over SNMP until the transition to the latest version is accomplished.⟧
- g.  Access control lists shall be implemented on SNMP managed NEs, where possible, to restrict access to only authorized NM operators and NM systems.
~~~~

Previous chunk 29:
~~~~text
[3.  NM USE OF SNMP]

- (1)  NEs requiring SNMP management shall be properly configured with appropriate read-only and read-write community names (commonly referred to as 'community strings').
- (2)  Read-only and read-write SNMP community strings for a managed device shall be different.
- (3)  Where possible, a different string (or strings) shall be utilized for each NE, or at minimum for each area of the network being managed.  For instance, if an authorized user requests access to information about DISN, they could be given a read-only community string and a list of devices that it can be used to access.  In addition to enabling access, this approach allows network managers to quickly and easily isolate portions of the network and serves to keep the number of required community strings to a manageable level.
- (4)  SNMP community strings shall be safeguarded and protected against compromise at the level of the operational network.
- (5)  SNMP community strings shall meet the minimum password length and composition requirements required by applicable security controls.
- (6)  The community strings and management passwords shall be changed at least annually and when there is a possibility that one has been compromised.
~~~~

## R040
Document: NIST.SP.800-125  |  chunk 78  |  page 25

Quote (the requirement text to judge):
> Ensure that virtual devices for the guest OS are associated only with the appropriate physical devices on the host system, such as the mappings between virtual and physical NICs.

Chunk 78 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4. Security Recommendations for Virtualization Components > 4.2 Guest OS Security]

-  Follow the recommended practices for managing the physical OS, e.g., time synchronization, log management, authentication, remote access, etc.
-  Install all updates to the guest OS promptly. All modern OSs have features that will automatically check for updates and install them.
-  Back up the virtual drives used by the guest OS on a regular basis, using the same policy for backups as is used for non-virtualized computers in the organization.
-  In each guest OS, disconnect unused virtual hardware. This is particularly important for virtual drives (usually virtual CDs and floppy drives), but is also important for virtual network adapters other than the primary network interface and serial and/or parallel ports.
-  Use separate authentication solutions for each guest OS unless there is a particular reason for two guest OSs to share credentials.
-  ⟦Ensure that virtual devices for the guest OS are associated only with the appropriate physical devices on the host system, such as the mappings between virtual and physical NICs.⟧
~~~~

Previous chunk 77:
~~~~text
[4. Security Recommendations for Virtualization Components > 4.2 Guest OS Security]

Many hosted virtualization systems also allow guest OSs to share information with the host OS through clipboard sharing. That is, copying information to the clipboard in the host OS allows that information to be pasted in the guest OS, and vice versa. Similarly, putting information on the clipboard in one guest OS makes the same information show up on the clipboard in other guest OSs running on the same hypervisor. This is a handy feature for users, but it is also a vector for attacks between the guest OS and host OS. Because of this, organizations should have policies regarding the use of shared clipboards.
The following are security recommendations for the guest OS itself:
~~~~

## R041
Document: DODI 8410.03  |  chunk 29  |  page 16

Quote (the requirement text to judge):
> (3) Where possible, a different string (or strings) shall be utilized for each NE, or at minimum for each area of the network being managed.

Chunk 29 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[3.  NM USE OF SNMP]

- (1)  NEs requiring SNMP management shall be properly configured with appropriate read-only and read-write community names (commonly referred to as 'community strings').
- (2)  Read-only and read-write SNMP community strings for a managed device shall be different.
- ⟦(3)  Where possible, a different string (or strings) shall be utilized for each NE, or at minimum for each area of the network being managed.⟧  For instance, if an authorized user requests access to information about DISN, they could be given a read-only community string and a list of devices that it can be used to access.  In addition to enabling access, this approach allows network managers to quickly and easily isolate portions of the network and serves to keep the number of required community strings to a manageable level.
- (4)  SNMP community strings shall be safeguarded and protected against compromise at the level of the operational network.
- (5)  SNMP community strings shall meet the minimum password length and composition requirements required by applicable security controls.
- (6)  The community strings and management passwords shall be changed at least annually and when there is a possibility that one has been compromised.
~~~~

Previous chunk 28:
~~~~text
[3.  NM USE OF SNMP]

- a.  All SNMP MIBs used in the DoD shall comply with technical standards in the DISR and DISA Security Technical Implementation Guides (STIGs).
- b.  All MIBs along with full descriptions of their use and format shall be stored in an MIB registry managed and published by DISA.
- c.  Where possible, elements in multiple MIBs that refer to the same parameter shall be formatted and identified the same way.  Standard formats and identifications shall be maintained in a DoD-published MIB data format and dictionary established and maintained by DISA.
- d.  New SNMP managed resources and management applications shall use the latest approved version of SNMP, to take advantage of the additional security features provided with this version of the protocol.  Existing systems that use SNMP shall transition to the latest approved SNMP version when feasible.
- e.  The latest version of SNMP shall be implemented with a security model appropriate to the security of the network rather than the default model.
- f.  Existing systems that use SNMP v1 or v2c shall implement the following security precautions in the period prior to transition to the latest approved version of SNMP:
~~~~

## R042
Document: afman17-2101  |  chunk 44  |  page 15

Quote (the requirement text to judge):
> AFO's will update at the start of each fiscal year the funding PDC with a certified MORD number, Line of Accounting (LOA), and Customer Account Information in TIBI

Chunk 44 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[ROLES AND RESPONSIBILITIES > 2.10. Authorized Funding Official (AFO) for organizations who fund and own DISN AF LHC circuits and/or services must: > 2.10.1.1.  AFO's will:]

- 2.10.1.1.1.  Update at the start of each fiscal  year the funding PDC with a certified MORD number, Line of Accounting (LOA), and Customer Account Information in TIBI  (T-0)
- 2.10.1.1.2.  Approve and/or disapprove DISA StoreFront Service Requests.
- 2.10.1.1.3.  Reconcile LHC  invoices  for all  DISN  ordered  telecommunications equipment and services, CSA's and/or other acquisition documents before authorizing payment. (T-0)
- 2.10.1.1.4.  Submit  PDC  requests  to  38  CYRS/SCC  Financial  Analyst  point  of contact.
- 2.10.1.1.5.  Validate  OSD/DITCO  Quarterly  Statistical  Sampling  invoice  in  TIBI when requested by 38 CYRS/SCC Financial Analyst. (T-0)
~~~~

Previous chunk 43:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.10. Authorized Funding Official (AFO) for organizations who fund and own DISN AF LHC circuits and/or services must:]

- 2.10.1.  Appoint an AFO in writing to their Headquarters level LAFO. An AFO is a civilian or military personnel at unit level responsible for approving and managing LHC funding for circuits and services. AFOs can only request access to their assigned PDC's.
~~~~

## R043
Document: DODI 8410.03  |  chunk 15  |  page 10

Quote (the requirement text to judge):
> The Heads of the DoD Components shall: Execute NM within the portions of the Defense Information Enterprise within their assigned area of responsibility (AOR) IAW Reference (b) and in support of Combatant Commanders' responsibilities.

Chunk 15 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[4.  DIRECTOR, OPERATIONAL TEST AND EVALUATION (DOT&E).  The DOT&E shall:]

7.  DIRECTOR, NATIONAL SECURITY AGENCY (DIRNSA)/CHIEF, CENTRAL SECURITY SERVICE (CHCSS).  The DIRNSA/CHCSS, under the authority, direction, and control of the USD(I), in addition to the responsibilities in sections 8 and 9 of this enclosure, and, consistent with the National Manager responsibilities assigned to DIRNSA by National Security Directive 42 (Reference (q)), shall lead, with the support of the other DoD Components, the development of suitable technical standards; administrative guidance; key-management protocols, devices, and systems; encryption methods; and other items as required to enable NM systems and the NE they manage to comply with applicable security controls.
8. HEADS OF THE DEFENSE INTELLIGENCE COMPONENTS.  The Heads of the Defense Intelligence Components shall execute their NM responsibilities consistent with Intelligence Community Directive 502 (Reference (r)).
9.  HEADS OF THE DoD COMPONENTS.  The Heads of the DoD Components shall:
- a.  Execute NM within the portions of the Defense Information Enterprise within their assigned area of responsibility (AOR) IAW Reference (b) and in support of Combatant Commanders' responsibilities.
~~~~

Previous chunk 14:
~~~~text
[4.  DIRECTOR, OPERATIONAL TEST AND EVALUATION (DOT&E).  The DOT&E shall:]

- a.  Ensure processes, procedures, and infrastructure are available to operationally test and evaluate NM capabilities that are developed and acquired.
- b.  Conduct periodic assessments of NM processes, procedures, and capabilities as requested by the DoD CIO.
5.  UNDER SECRETARY OF DEFENSE FOR INTELLIGENCE (USD(I)).  The USD(I) shall serve as the DoD focal point to the Intelligence Community (IC) for NM policy and oversight matters relating to intelligence information sharing and interoperability of Defense intelligence systems and processes IAW DoDD 5143.01 (Reference (o)).
6.  DIRECTOR, DEFENSE INTELLIGENCE AGENCY (DIA).  The Director, DIA, under the authority, direction, and control of the USD(I) and as the Manager of the SCI component of the GIG shall, in addition to the responsibilities in sections 8 and 9 of this enclosure, interact with the Director of National Intelligence to facilitate coordination and sharing of DoD SCI network status and SA information IAW the memorandum of agreement between the DoD CIO and the IC CIO (Reference (p)).
~~~~

## R044
Document: DODI 8410.03  |  chunk 32  |  page 17

Quote (the requirement text to judge):
> This section must include: where, how, and in what format NM information and data will be collected; how often it will be collected; how it will be shared with the customer; how often it will be shared with the customer; how NM information and data will be archived; and duration archived information will be retained IAW Reference (h).

Chunk 32 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4.  SLAs]

- (5)  How NM service levels will be monitored and reported.  ⟦This section must include: where, how, and in what format NM information and data will be collected; how often it will be collected; how it will be shared with the customer; how often it will be shared with the customer; how NM information and data will be archived; and duration archived information will be retained IAW Reference (h).⟧  This section will define for all parties:
8. (a)  The characteristics of the NM information to be exchanged (e.g., data schema(s) used, specialized data formatting (if any), and any non-standard characteristics).
~~~~

Previous chunk 31:
~~~~text
[4.  SLAs]

- a.  NM systems shall be located within the network topology in a manner that ensures they can monitor and report on SLA compliance.
- b.  NM SLAs shall at a minimum address the following areas identified in International Telecommunications Union - Telecommunications Recommendation M.3342 (Reference (z)) and TM Forum GB917 Release 3.0 (Reference (aa)):
- (1)  Identification of the organizations between which the agreement is established, to include technical and organizational points of contact.
- (2)  A description of the NM services that will be provided along with scope, limitations, and other terms of reference that might be needed.
- (3)  A basic description of the NM system and supporting equipment information and who is responsible for providing, maintaining, and operating it.
- (4)  Detailed explanations of the expected levels and quality of NM services that will be provided.
~~~~

## R045
Document: DODI 8410.03  |  chunk 21  |  page 12

Quote (the requirement text to judge):
> Develop, in coordination with the other Heads of the DoD Components, automated CM and PBNM operational requirements.

Chunk 21 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4.  DIRECTOR, OPERATIONAL TEST AND EVALUATION (DOT&E).  The DOT&E shall:]

12.  CDRUSSTRATCOM.  The CDRUSSTRATCOM, in addition to the responsibilities in sections 8 and 10 of this enclosure, shall:
- a.  Develop and issue guidance for ensuring uninterrupted, end-to-end monitoring and control of all operational DoD networks.
- b.  Develop, publish, and enforce standard processes for the sharing of NM data about readiness and operating status of all DoD networks.
- c.  Establish clear lines of authority and responsibility for NM across all DoD network domains and with DoD mission partners.
- d.  Develop, in coordination with the Director, DISA, operational guidance for integrating and correlating NM capabilities to enable near real-time end-to-end network SA.
- e.  Develop, in coordination with the other Heads of the DoD Components, and issue security classification guidelines for NM and SM information IAW DoDM 5200.01, Volume 1 (Reference (t)).
- f.  Approve NM data schemas and sharing mechanisms.
- g.  ⟦Develop, in coordination with the other Heads of the DoD Components, automated CM and PBNM operational requirements.⟧
~~~~

Previous chunk 20:
~~~~text
[4.  DIRECTOR, OPERATIONAL TEST AND EVALUATION (DOT&E).  The DOT&E shall:]

- k.  Provide the NM and SM data necessary to fulfill the commander's critical information requirements in support of established DoD cyberspace operational hierarchies.
- l.  Ensure, in coordination with DISA, all DoD equipment containing or potentially containing personally identifiable information and other data of a sensitive nature is managed in accordance with DoDI 5000.64 (Reference (s)).
10.  CJCS.  The CJCS, in addition to the responsibilities in section 8 of this enclosure and in coordination with the other Heads of the DoD Components, shall:
- a.  Establish and issue priorities for the collection and sharing of NM data.
- b.  Develop and promulgate joint NM tactics, techniques, and procedures.
- c.  In coordination with the Combatant Commanders, establish requirements for sharing NM information and data with coalition partner networks.
11.  COMMANDERS OF THE COMBATANT COMMANDS.  The Commanders of the Combatant Commands, in addition to the responsibilities in section 8 of this enclosure, shall support the Joint Staff in establishing requirements for sharing NM information and data with coalition partner networks.
~~~~

## R046
Document: DODI 8410.03  |  chunk 12  |  page 9

Quote (the requirement text to judge):
> The DoD CIO, shall develop and promulgate technical guidance and architectures for developing and implementing automated CM and PBNM systems.

Chunk 12 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- j.  Develop and promulgate DoD-wide standards and guidelines for use of NM protocols (such as SNMP or network configuration protocol) for communication of NM information between NM systems and their managed network elements (NEs).
- k.  Develop, in coordination with the Commander, U.S. Strategic Command (USSTRATCOM), technical guidance for integrating and correlating NM and SM capabilities to enable near real-time end-to-end network SA throughout the GIG.
- l.  Support the USD(AT&L) in reviewing and studying automated CM and PBNM capabilities and standards.
- m.  Develop and promulgate technical guidance and architectures for developing and implementing automated CM and PBNM systems.
- n.  Establish and maintain a central repository of SLAs.
~~~~

Previous chunk 11:
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- g.  Create, manage, and maintain a common repository based upon security classifications within the MDR for all data-exchange schemas and SNMP MIBs used by NM systems, including supporting documentation and interface characteristics and specifications.
- h.  Participate in applicable standards bodies and organizations to advocate for and aid in developing standards, protocols, and mechanisms for translating NM information from current formats (e.g., SNMP) to ones that facilitate net-centric information sharing (e.g., extensible markup language).
- i.  Develop, in coordination with the DoD Components, a GIG technical profile (GTP) to define the interface specifications for exchanging data between NM systems.
~~~~

## R047
Document: DODI 8410.03  |  chunk 37  |  page 19

Quote (the requirement text to judge):
> Access to NM systems shall be authorized by the appropriate unit level commander responsible for the NM system. Only those users with proper credentials and access authorizations will be granted access to NM systems.

Chunk 37 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[5.  NM SECURITY]

- c.  NM system operator and supervisory positions (e.g., system administrators, network managers and controllers, router and switch administrators, managers and controllers) performing NM IA functions as defined in DoD 8570.01-M (Reference (ad)) shall be designated IA Technical Category Level 2 and IA Management Category Level 2 positions and as critical sensitive positions as defined by DoD 5200.2-R (Reference (ae)), and military, government civilian, and contractor personnel filling them shall meet all required background checks, training, and certification requirements prior to assuming their duties.
- d.  ⟦Access to NM systems shall be authorized by the appropriate unit level commander responsible for the NM system.  Only those users with proper credentials and access authorizations will be granted access to NM systems.⟧  NM system users shall comply with the applicable cybersecurity training and certification requirements IAW Reference (ad).
- e.  NM functions are critical within the network infrastructure.  Accordingly, supply chain risk management shall be applied to the acquisition of NM functionality IAW DoDI 5200.44 (Reference (af)) and DoDI 5200.39 (Reference (ag)).
~~~~

Previous chunk 36:
~~~~text
[5.  NM SECURITY]

- a.  Data exchanges between NM systems shall be encrypted per DISA Security Technical Implementation Guides Network Infrastructure (Reference (ab)) and shall be processed and protected at the appropriate classification level.
- b.  Management information obtained from NEs shall be classified, stored, processed, and shared IAW the USSTRATCOM GIG NetOps Security Classification Guide (Reference (ac)) and other applicable classification guides.  NM data that provides sensitive operational status of the network or the status of the network's ability to support real-world operations shall be protected as sensitive information (minimum) or at an appropriate higher classification level based on the classification of the network it is derived from.
~~~~

## R048
Document: afman17-2101  |  chunk 37  |  page 13

Quote (the requirement text to judge):
> Register, at a minimum, two Authorized Requesting Officials in DISA StoreFront provisioning tool who: Prepare, submit, manage, and track Service Requests (SRs) in DISA StoreFront for long-haul comm circuits, services, Networx/ Enterprise Infrastructure Solutions requirements and equipment requests for the Base and supported Geographically Separated Units (GSU) that receive AF LHC services from the installation.

Chunk 37 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.3.2.  Register, at a minimum,  two  Authorized Requesting Officials in  DISA StoreFront provisioning tool who:
- 2.8.3.2.1.  Prepare,  submit,  manage,  and  track  Service  Requests  (SRs)  in  DISA StoreFront for long-haul comm circuits, services, Networx/ Enterprise Infrastructure Solutions    requirements    and    equipment    requests  for  the  Base  and  supported Geographically  Separated  Units  (GSU)  that  receive      AF  LHC  services  from  the installation.
- 2.8.3.3.  TCF's and PTF's must establish and maintain:
- 2.8.3.3.1.  Provisioning records and permanent/temporary circuit history folders.
- 2.8.3.3.2.  Site specific systems diagrams that depict signal flow  through the facility readily available in the operations area of the Tech Control Facility (TCF), Patch and Test  Facility  (PTF),  or  Network  Control  Center  (NCC)  to  aid  restoration  and troubleshooting efforts.
~~~~

Previous chunk 36:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.2.7.1.  Ensure DOD CIO endorsed DISA/DITCO policy is followed which states zero  tolerance  for  expired  CSAs.  DISA/DITCO  intent  is  to  issue  vendors  a  nonrevocable termination letter within two weeks of CSA expiration date.
- 2.8.3.  Technical  Control  Facility  (TCF),  Patch  and  Test  Facility  (PTF),  and/or  Circuit Actions.
- 2.8.3.1.  Responsible for base LHC management in accordance with all DOD Directives and Instructions, DISA Circulars (DISACs), DISA Notices, and AF policies.
- 2.8.3.1.1.  Technical  Control  Facilities  and  Patch  and  Test  Facilities  in  the  Pacific area  should  follow  the  Pacific  area  guidance  in  DISAC  310-70-1  DISA  PAC Supplement 1 and DISA PAC C 310-70-58 along with other DISA PAC circulars as they apply.
- 2.8.3.1.2.  TCFs identified as Facility Control Offices or Intermediate Facility Control Offices should follow DISAC 310-70-1 DISA PAC Supplement 1 guidance.
~~~~

## R049
Document: DODI 8410.03  |  chunk 36  |  page 19

Quote (the requirement text to judge):
> Management information obtained from NEs shall be classified, stored, processed, and shared IAW the USSTRATCOM GIG NetOps Security Classification Guide (Reference (ac)) and other applicable classification guides.  NM data that provides sensitive operational status of the network or the status of the network's ability to support real-world operations shall be protected as sensitive information (minimum) or at an appropriate higher classification level based on the classification of the network it is derived from.

Chunk 36 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[5.  NM SECURITY]

- a.  Data exchanges between NM systems shall be encrypted per DISA Security Technical Implementation Guides Network Infrastructure (Reference (ab)) and shall be processed and protected at the appropriate classification level.
- b.  ⟦Management information obtained from NEs shall be classified, stored, processed, and shared IAW the USSTRATCOM GIG NetOps Security Classification Guide (Reference (ac)) and other applicable classification guides.  NM data that provides sensitive operational status of the network or the status of the network's ability to support real-world operations shall be protected as sensitive information (minimum) or at an appropriate higher classification level based on the classification of the network it is derived from.⟧
~~~~

Previous chunk 35:
~~~~text
[4.  SLAs]

- (4)  Mean time to repair failures in network equipment or connectivity.
- (5)  Throughput of a given network node, by traffic type.
- (6)  Percentage of available bandwidth consumed on a given link, by traffic type.
- (7)  Fault status, by node priority.
- (8)  Packet error rate and bit error rate (average and standard deviation) through a given network node.
- (9)  Quality of service requirements for NM and control plane traffic.
~~~~

## R050
Document: NIST.SP.800-125  |  chunk 42  |  page 16

Quote (the requirement text to judge):
> enforce security requirements

Chunk 42 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[2. Introduction to Full Virtualization > 2.4 Full Virtualization Use Cases > 2.4.1 Server Virtualization > 2.4.1.2 Multiple Server Virtualization]

For many years, organizations have typically deployed each important service to its own dedicated host so as to better isolate each server from the others and prevent a compromise of one server or host from granting control to other servers. However, having many hosts is costly (space, power consumption, maintenance, hardware, etc.), so organizations have been adopting server virtualization so that they can host multiple services on a single host, with each service in a separate guest OS to ⟦enforce security requirements⟧. When a service experiences higher-than-normal use, the hypervisor can coordinate requests among guest OSs and other hypervisors to ensure that resources are properly distributed. Services that are rarely used can be kept in a saved state by the guest OS and loaded by the guest OS on demand. This frees up resources for other guest OSs. Also, new servers can be deployed without the need to configure and deploy as much new dedicated hardware.
~~~~

Previous chunk 41:
~~~~text
[2. Introduction to Full Virtualization > 2.4 Full Virtualization Use Cases > 2.4.1 Server Virtualization > 2.4.1.1 Single Server Virtualization]

A common use case for single server virtualization is supporting a service that only runs on a legacy OS that cannot be properly secured on its own. For example, common security controls may not be available for the legacy OS. If the service and legacy OS are run as a guest OS, the hypervisor or host OS may be able to monitor the guest OS's actions using various security controls that the legacy OS itself cannot. Also, an additional layer of authentication and auditing could be added, such as at the host OS level. Such monitoring can be built into the organization's security policies.
~~~~

## R051
Document: NIST.SP.800-125  |  chunk 69  |  page 23

Quote (the requirement text to judge):
> The access options vary based on hypervisor type.

Chunk 69 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4. Security Recommendations for Virtualization Components > 4.1 Hypervisor Security]

Because of the hypervisor's level of access to and control over the guest OSs, limiting access to the hypervisor is critical to the security of the entire system. ⟦The access options vary based on hypervisor type.⟧ Most bare metal hypervisors have access controls to the system. Typically, the access method is just username and password, but some bare metal hypervisors offer additional controls such as hardware token-based authentication to grant access to the hypervisor's management interface. On some systems, there are different levels of authorization, such as allowing some users to view logs but not be able to change any settings or interact directly with the guest OSs. These view-only user accounts allow auditors and others to have sufficient access to meet their needs without reducing overall security.
~~~~

Previous chunk 68:
~~~~text
[4. Security Recommendations for Virtualization Components > 4.1 Hypervisor Security]

Hypervisors can be managed in different ways, with some hypervisors allowing management through multiple methods. It is important to secure each hypervisor management interface, both locally and remotely accessible. The capability for remote administration can usually be enabled or disabled in the virtualization management system. If remote administration is enabled in a hypervisor, access to all remote administration interfaces should be restricted by a firewall. Also, hypervisor management communications should be protected. One option is to have a dedicated management network that is separate from all other networks and that can only be accessed by authorized administrators. Management communications carried on untrusted networks must be encrypted using FIPS-approved methods, provided by either the virtualization solution or a third-party solution, such as a virtual private network (VPN) that encapsulates the management traffic.
~~~~

## R052
Document: DODI 8410.03  |  chunk 33  |  page 18

Quote (the requirement text to judge):
> A description of NM system backup, recovery and continuity of operations requirement.

Chunk 33 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4.  SLAs]

- (b)  Required NM data update rates.
- (c)  Maximum allowable time from when an event takes place to when it is reported by the NM system, as well as the location of event.
- (d)  Location of the NM event.
- (e)  Allowable NM system initialization time and data sync (or data re-sync due to NM and radio reconnection).
- (f)  Required local event storage requirements (if any).
- (g)  Reporting formats, destinations, and update rates (if finished reports are to be provided.
- (h)  Mechanisms for enforcement, auditing, and assurance.
- (6)  ⟦A description of NM system backup, recovery and continuity of operations requirement.⟧
- (7)  Procedures for changing and terminating the SLA.
- (8)  A description of the remedies available to the customer in the event the NM system does not perform as agreed.
~~~~

Previous chunk 32:
~~~~text
[4.  SLAs]

- (5)  How NM service levels will be monitored and reported.  This section must include: where, how, and in what format NM information and data will be collected; how often it will be collected; how it will be shared with the customer; how often it will be shared with the customer; how NM information and data will be archived; and duration archived information will be retained IAW Reference (h).  This section will define for all parties:
8. (a)  The characteristics of the NM information to be exchanged (e.g., data schema(s) used, specialized data formatting (if any), and any non-standard characteristics).
~~~~

## R053
Document: NIST.SP.800-125  |  chunk 104  |  page 32

Quote (the requirement text to judge):
> the organization should remove any sensitive data from the host

Chunk 104 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[5. Secure Virtualization Planning and Deployment > 5.5 Disposition]

Before a device using virtualization permanently leaves an organization (such as when a leased server's lease expires or when an obsolete PC is being recycled), ⟦the organization should remove any sensitive data from the host⟧. Data may also need to be wiped if an organization provides 'loaner' devices to teleworkers, particularly for travel. The task of scrubbing all sensitive data from storage devices is often surprisingly difficult because of all the places where such data resides. See NIST SP 800-88, Guidelines for Media Sanitization , for additional information and recommendations on removing data from devices. Note that sensitive data may be found nearly anywhere on a device because of the nature of virtualization. An organization should strongly consider erasing all storage devices completely.
~~~~

Previous chunk 103:
~~~~text
[5. Secure Virtualization Planning and Deployment > 5.4 Operations and Maintenance]

-  Control. Reconfigure access control features as needed based on factors such as policy changes, technology changes, audit findings, and new security needs
-  Logging. Document anomalies detected within the virtualized environment. Such anomalies might indicate malicious activity or deviations from policy and procedures. Anomalies should be reported to other systems' administrators as appropriate.
Organizations should periodically perform assessments to confirm that the organization's virtualization policies, processes, and procedures are being followed properly. Assessment activities may be passive, such as reviewing logs, or active, such as performing vulnerability scans and penetration testing. Assessments need to be made at all levels of the virtualized infrastructure, including the host and guest OSs, the hypervisor, and shared storage media. More information on technical assessments is available from NIST SP 800-115, Technical Guide to Information Security Testing and Assessment .
~~~~

## R054
Document: afman17-2101  |  chunk 58  |  page 19

Quote (the requirement text to judge):
> Authorizing Official Approval is required for AETC and USAFA operated education and training academic networks.

Chunk 58 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[COMMERCIAL INTERNET SERVICE PROVIDER (ISP) > 3.1. Commercial Internet Service Provider (CISP) Connection]

3.1.1.2.5.  Headquarters Air Education and Training Command (HQ AETC) and the United  States  AF  Academy  (USAFA).  HQ  AETC  and  USAFA  require  academic networks that provide students, faculty, and staff IT services that are not available on the AFNET (i.e., conduct research and scientific collaborations). Consequently, HQ AETC and USAFA are authorized to operate networks specifically  designed  to  IT enable their education and training missions.
3.1.1.2.5.1.  ⟦Authorizing  Official  Approval  is  required  for  AETC  and  USAFA operated education and training academic networks.⟧
3.1.1.2.5.2.  AETC and USAFA  operated  education and training academic networks  are  exempt  from  the  DoD  Information  Network  (DODIN)  Waiver process if they do not process, store, or transmit sensitive information.
~~~~

Previous chunk 57:
~~~~text
[COMMERCIAL INTERNET SERVICE PROVIDER (ISP) > 3.1. Commercial Internet Service Provider (CISP) Connection]

3.1.1.2.3.  Morale, Welfare and Recreation (MWR) Activities. Internet-based Capabilities  (IbCs)  are  generally  internet  services  for  military  exchanges,  internet cafes, and lodging programs, provided by MWRs, for use by authorized patrons, see DoDI 8550.01, DoD Internet Services and Internet-Based Capabilities, for guidance. Other  examples of IbCs include Wounded  Warrior  housing, hospitals/clinics, Wounded Warrior fundraising events, etc.
3.1.1.2.4.  DoD Dependent Schools and Base Education Offices. Internet access for classroom education or civilian education institutions must be through a commercial ISP (or DISAs Private ISP when available) and cannot be connected to NIPRNET.
~~~~

## R055
Document: NIST.SP.800-125  |  chunk 55  |  page 19

Quote (the requirement text to judge):
> Snapshots can be more risky than images because snapshots contain the contents of RAM memory at the time that the snapshot was taken, and this might include sensitive information that was not even stored on the drive itself.

Chunk 55 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[3. Virtualization Security Overview > 3.3 Image and Snapshot Management]

Creating guest machine images and snapshots does not affect the vulnerabilities within them, such as the vulnerabilities in the guest OSs, services, and applications. However, images and snapshots do affect security in several ways, some positive and some negative, and they also affect IT operations.
Note that one of the biggest security issues with images and snapshots is that they contain sensitive data (such as passwords, personal data, and so on) just like a physical hard drive. Because it is easier to move around an image or snapshot than a hard drive, it is more important to think about the security of the data in that image or snapshot. ⟦Snapshots can be more risky than images because snapshots contain the contents of RAM memory at the time that the snapshot was taken, and this might include sensitive information that was not even stored on the drive itself.⟧
~~~~

Previous chunk 54:
~~~~text
[3. Virtualization Security Overview > 3.2 Guest OS Monitoring]

The hypervisor is fully aware of the current state of each guest OS it controls. As such, the hypervisor may have the ability to monitor each guest OS as it is running, which is known as introspection . Introspection can provide full auditing capabilities that may otherwise be unavailable. Monitoring capabilities provided through introspection can include network traffic, memory, processes, and other elements of a guest OS. For many virtualization products, the hypervisor can incorporate additional security controls or interface with external security controls and provide information to them that was gathered through introspection. Examples include firewalling, intrusion detection, and access control. Many products also allow the security policy being enforced through hypervisor-based security controls to be moved as a guest OS is migrated from one physical host to another.
Network traffic monitoring is particularly important when networking is being performed between two guest OSs on the host or between a guest OS and the host OS. Under typical network configurations, this traffic does not pass through network-based security controls, so host-based security controls should be used to monitor the traffic instead.
~~~~

## R056
Document: NIST.SP.800-125  |  chunk 68  |  page 22

Quote (the requirement text to judge):
> Hypervisor management communications should be protected.

Chunk 68 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[4. Security Recommendations for Virtualization Components > 4.1 Hypervisor Security]

Hypervisors can be managed in different ways, with some hypervisors allowing management through multiple methods. It is important to secure each hypervisor management interface, both locally and remotely accessible. The capability for remote administration can usually be enabled or disabled in the virtualization management system. If remote administration is enabled in a hypervisor, access to all remote administration interfaces should be restricted by a firewall. Also, hypervisor management communications should be protected. One option is to have a dedicated management network that is separate from all other networks and that can only be accessed by authorized administrators. Management communications carried on untrusted networks must be encrypted using FIPS-approved methods, provided by either the virtualization solution or a third-party solution, such as a virtual private network (VPN) that encapsulates the management traffic.
~~~~

Previous chunk 67:
~~~~text
[4. Security Recommendations for Virtualization Components > 4.1 Hypervisor Security]

The programs that control the hypervisor should be secured using methods similar to those used to protect other software running on desktops and servers. The security of the entire virtual infrastructure relies on the security of the virtualization management system that controls the hypervisor and allows the operator to start guest OSs, create new guest OS images, and perform other actions. Because of the security implications of these actions, access to the virtualization management system should be restricted to authorized administrators only. Some virtualization management systems allow different level of access to different users, such as giving some users read-only access to the administrative interface of a guest OS, other users control over particular guest OSs, and yet other users complete administrative control. Most hypervisor software currently only uses passwords for access control; this may be too weak for some organizations' security policies and may require the use of compensating controls, such as a separate authentication system used for restricting access to the host on which the virtualization management system is installed.
~~~~

## R057
Document: NIST.SP.800-125  |  chunk 90  |  page 28

Quote (the requirement text to judge):
> developing virtualization policy

Chunk 90 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[5. Secure Virtualization Planning and Deployment]

-  Phase 1: Initiation. This phase includes the tasks that an organization should perform before it starts to design a virtualization solution. These include identifying needs for virtualization, providing an overall vision for how virtualization solutions would support the mission of the organization, creating a high-level strategy for implementing virtualization solutions, ⟦developing virtualization policy⟧, identifying platforms and applications that can be virtualized, and specifying business and functional requirements for the solution.
-  Phase 2: Planning and Design. In this phase, personnel specify the technical characteristics of the virtualization solution and related components. These include the authentication methods and the cryptographic mechanisms used to protect communications. At the end of this phase, solution components are procured.
-  Phase 3: Implementation. In this phase, equipment is configured to meet operational and security requirements, installed and tested as a prototype, and then activated on a production network. Implementation includes altering the configuration of other security controls and technologies, such as security event logging, network management, and authentication server integration.
-  Phase 4: Operations and Maintenance. This phase includes security-related tasks that an organization should perform on an ongoing basis once the virtualization solution is operational, including log review, attack detection, and incident response.
~~~~

Previous chunk 89:
~~~~text
[5. Secure Virtualization Planning and Deployment]

This section brings together the concepts presented in the previous sections of the guide and explains how they should be incorporated throughout the entire life cycle of virtualization solutions, involving everything from policy to operations. This section references a five-phase life cycle model to help organizations determine at what point in their virtualization deployments a recommendation may be relevant. This model is based on one introduced in NIST SP 800-64, Security Considerations in the Information System Development Life Cycle . Organizations may follow a project management methodology or life cycle model that does not directly map to the phases in the model presented here, but the types of tasks in the methodology and their sequencing are probably similar. The phases of the life cycle are as follows:
~~~~

## R058
Document: afman17-2101  |  chunk 44  |  page 15

Quote (the requirement text to judge):
> AFO's will submit PDC requests to 38 CYRS/SCC Financial Analyst point of contact

Chunk 44 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[ROLES AND RESPONSIBILITIES > 2.10. Authorized Funding Official (AFO) for organizations who fund and own DISN AF LHC circuits and/or services must: > 2.10.1.1.  AFO's will:]

- 2.10.1.1.1.  Update at the start of each fiscal  year the funding PDC with a certified MORD number, Line of Accounting (LOA), and Customer Account Information in TIBI  (T-0)
- 2.10.1.1.2.  Approve and/or disapprove DISA StoreFront Service Requests.
- 2.10.1.1.3.  Reconcile LHC  invoices  for all  DISN  ordered  telecommunications equipment and services, CSA's and/or other acquisition documents before authorizing payment. (T-0)
- 2.10.1.1.4.  Submit  PDC  requests  to  38  CYRS/SCC  Financial  Analyst  point  of contact.
- 2.10.1.1.5.  Validate  OSD/DITCO  Quarterly  Statistical  Sampling  invoice  in  TIBI when requested by 38 CYRS/SCC Financial Analyst. (T-0)
~~~~

Previous chunk 43:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.10. Authorized Funding Official (AFO) for organizations who fund and own DISN AF LHC circuits and/or services must:]

- 2.10.1.  Appoint an AFO in writing to their Headquarters level LAFO. An AFO is a civilian or military personnel at unit level responsible for approving and managing LHC funding for circuits and services. AFOs can only request access to their assigned PDC's.
~~~~

## R059
Document: afman17-2101  |  chunk 61  |  page 20

Quote (the requirement text to judge):
> Configure wireless technologies (access points, routers, cellular 'hot spot' devices) for Wi-Fi Protected Access version 2 (WPA2) encryption.

Chunk 61 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[COMMERCIAL INTERNET SERVICE PROVIDER (ISP) > 3.1. Commercial Internet Service Provider (CISP) Connection]

3.1.1.3.2.3.  ⟦Configure wireless technologies (access points, routers, cellular 'hot spot' devices) for Wi-Fi Protected Access version 2 (WPA2) encryption.⟧
3.2. Air Education and Training Command (HQ AETC) and the United States Air Force Academy (USAFA) are authorized to operate networks specifically designed to IT enable their  education  and  training  missions. AETC  and  USAFA  require  academic  networks  that provide students, faculty, and staff IT services that are not available on the Air Force Network (i.e. to conduct research and scientific collaboration).
3.2.1.  Authorizing Official Approval is required for AETC and USAFA operated education and training academic networks.
3.2.2.  AETC and USAFA operated education and training academic networks are exempt from the DoD Information Network (DODIN) Waiver process if they do not process, store, or transmit sensitive information.
~~~~

Previous chunk 60:
~~~~text
[COMMERCIAL INTERNET SERVICE PROVIDER (ISP) > 3.1. Commercial Internet Service Provider (CISP) Connection]

3.1.1.3.1.  Protect  controlled  DoD,  Personally  Identifiable  Information  (PII),  Law Enforcement,  and  Criminal  Investigative  information  from  access  by  unauthorized personnel using role-based access methodology and FIPS 140-2 encryption for data in transit.
3.1.1.3.2.  The  CISP  connection  complies  with  applicable  STIGs,  SRGs,  and  other DoD cyber security policies when the application of those policies and standards will not adversely affect the mission need for the CISP.
3.1.1.3.2.1.  The  authorized  Cyber  Security  Service  Provider  (CSSP)  or  other monitoring  solution  appropriate  for  the  mission  monitors  the  CISP  used  for controlled unclassified information (CUI) in accordance with STIGs, SRGs, and other DoD cyber security policies.
3.1.1.3.2.2.  Perform annual reviews to determine if they are still needed and for compliance with the security controls and the authorization to operate (ATO).
~~~~

## R060
Document: DODI 8410.03  |  chunk 12  |  page 9

Quote (the requirement text to judge):
> The DoD CIO, shall develop, in coordination with the Commander, U.S. Strategic Command (USSTRATCOM), technical guidance for integrating and correlating NM and SM capabilities to enable near real-time end-to-end network SA throughout the GIG.

Chunk 12 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- j.  Develop and promulgate DoD-wide standards and guidelines for use of NM protocols (such as SNMP or network configuration protocol) for communication of NM information between NM systems and their managed network elements (NEs).
- k.  Develop, in coordination with the Commander, U.S. Strategic Command (USSTRATCOM), technical guidance for integrating and correlating NM and SM capabilities to enable near real-time end-to-end network SA throughout the GIG.
- l.  Support the USD(AT&L) in reviewing and studying automated CM and PBNM capabilities and standards.
- m.  Develop and promulgate technical guidance and architectures for developing and implementing automated CM and PBNM systems.
- n.  Establish and maintain a central repository of SLAs.
~~~~

Previous chunk 11:
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- g.  Create, manage, and maintain a common repository based upon security classifications within the MDR for all data-exchange schemas and SNMP MIBs used by NM systems, including supporting documentation and interface characteristics and specifications.
- h.  Participate in applicable standards bodies and organizations to advocate for and aid in developing standards, protocols, and mechanisms for translating NM information from current formats (e.g., SNMP) to ones that facilitate net-centric information sharing (e.g., extensible markup language).
- i.  Develop, in coordination with the DoD Components, a GIG technical profile (GTP) to define the interface specifications for exchanging data between NM systems.
~~~~

## R061
Document: NIST.SP.800-125  |  chunk 90  |  page 28

Quote (the requirement text to judge):
> log review, attack detection, and incident response

Chunk 90 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[5. Secure Virtualization Planning and Deployment]

-  Phase 1: Initiation. This phase includes the tasks that an organization should perform before it starts to design a virtualization solution. These include identifying needs for virtualization, providing an overall vision for how virtualization solutions would support the mission of the organization, creating a high-level strategy for implementing virtualization solutions, developing virtualization policy, identifying platforms and applications that can be virtualized, and specifying business and functional requirements for the solution.
-  Phase 2: Planning and Design. In this phase, personnel specify the technical characteristics of the virtualization solution and related components. These include the authentication methods and the cryptographic mechanisms used to protect communications. At the end of this phase, solution components are procured.
-  Phase 3: Implementation. In this phase, equipment is configured to meet operational and security requirements, installed and tested as a prototype, and then activated on a production network. Implementation includes altering the configuration of other security controls and technologies, such as security event logging, network management, and authentication server integration.
-  Phase 4: Operations and Maintenance. This phase includes security-related tasks that an organization should perform on an ongoing basis once the virtualization solution is operational, including ⟦log review, attack detection, and incident response⟧.
~~~~

Previous chunk 89:
~~~~text
[5. Secure Virtualization Planning and Deployment]

This section brings together the concepts presented in the previous sections of the guide and explains how they should be incorporated throughout the entire life cycle of virtualization solutions, involving everything from policy to operations. This section references a five-phase life cycle model to help organizations determine at what point in their virtualization deployments a recommendation may be relevant. This model is based on one introduced in NIST SP 800-64, Security Considerations in the Information System Development Life Cycle . Organizations may follow a project management methodology or life cycle model that does not directly map to the phases in the model presented here, but the types of tasks in the methodology and their sequencing are probably similar. The phases of the life cycle are as follows:
~~~~

## R062
Document: NIST.SP.800-125  |  chunk 12  |  page 7

Quote (the requirement text to judge):
> Security should be considered from the initial planning stage at the beginning of the systems development life cycle to maximize security and minimize costs.

Chunk 12 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[Carefully plan the security for a full virtualization solution before installing, configuring, and deploying it.]

Planning helps ensure that the virtual environment is as secure as possible and in compliance with all relevant organizational policies. ⟦Security should be considered from the initial planning stage at the beginning of the systems development life cycle to maximize security and minimize costs.⟧ It is much more difficult and expensive to address security after deployment and implementation.
~~~~

Previous chunk 11:
~~~~text
[Ensure that the hypervisor is properly secured.]

Securing a hypervisor involves actions that are standard for any type of software, such as installing updates as they become available. Other recommended actions that are specific to hypervisors include disabling unused virtual hardware; disabling unneeded hypervisor services such as clipboard- or filesharing; and considering using the hypervisor's capabilities to monitor the security of each guest OS running within it, as well as the security of activity occurring between guest OSs. The hypervisor itself also needs to be carefully monitored for signs of compromise. It is also important to provide physical access controls for the hardware on which the hypervisor runs. For example, hosted hypervisors are typically controlled by management software that can be used by anyone with access to the keyboard and mouse. Even bare metal hypervisors require physical security: someone who can reboot the host computer that the hypervisor is running on might be able to alter some of the security settings for the hypervisor.
~~~~

## R063
Document: DODI 8410.03  |  chunk 33  |  page 18

Quote (the requirement text to judge):
> Maximum allowable time from when an event takes place to when it is reported by the NM system, as well as the location of event.

Chunk 33 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[4.  SLAs]

- (b)  Required NM data update rates.
- (c)  ⟦Maximum allowable time from when an event takes place to when it is reported by the NM system, as well as the location of event.⟧
- (d)  Location of the NM event.
- (e)  Allowable NM system initialization time and data sync (or data re-sync due to NM and radio reconnection).
- (f)  Required local event storage requirements (if any).
- (g)  Reporting formats, destinations, and update rates (if finished reports are to be provided.
- (h)  Mechanisms for enforcement, auditing, and assurance.
- (6)  A description of NM system backup, recovery and continuity of operations requirement.
- (7)  Procedures for changing and terminating the SLA.
- (8)  A description of the remedies available to the customer in the event the NM system does not perform as agreed.
~~~~

Previous chunk 32:
~~~~text
[4.  SLAs]

- (5)  How NM service levels will be monitored and reported.  This section must include: where, how, and in what format NM information and data will be collected; how often it will be collected; how it will be shared with the customer; how often it will be shared with the customer; how NM information and data will be archived; and duration archived information will be retained IAW Reference (h).  This section will define for all parties:
8. (a)  The characteristics of the NM information to be exchanged (e.g., data schema(s) used, specialized data formatting (if any), and any non-standard characteristics).
~~~~

## R064
Document: afman17-2101  |  chunk 15  |  page 7

Quote (the requirement text to judge):
> Ensure their technical control facilities perform network control and reconfiguration.

Chunk 15 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[ROLES AND RESPONSIBILITIES]

2.1.4.  Centrally  manage,  procure,  operate,  manage,  and  maintain  their  portion  of  the DODIN, and the supporting infrastructure, establish, and extend AFIN services.
2.1.5.  Per  Joint  Pub  6-0  -  Service  components  and  assigned  support  organizations  should designate a single office within their communications staffs to coordinate with joint force J-6. All Service component communication support organizations should:
2.1.5.1.  Formulate and publish plans, orders, and internal operating instructions for the use of their communications systems.
2.1.5.2.  ⟦Ensure their technical control facilities perform network control and reconfiguration.⟧ For example, they change circuit paths, direct troubleshooting to resolve problems, and provide status information.
2.1.5.3.  Account  for  traffic  management  in  a  packet-routed  environment  and  execute circuit management functions.
~~~~

Previous chunk 14:
~~~~text
[ROLES AND RESPONSIBILITIES]

2.1. Air Force. The Department of the Air Force in accordance with DOD Directive 5100.01 shall  organize,  train,  equip,  and  provide  air,  space,  and  cyberspace  forces  for  the  conduct  of prompt  and  sustained  combat  operations,  military  engagement,  and  security  cooperation  in defense of the Nation, and to support the other  Military Services and joint forces.  Long Haul Communication is an enabler for air, space and cyberspace forces, the Air Force responsibilities for DISN LHC are:
2.1.1.  Program,  budget,  fund,  and  provide  support  for  the  DISN,  and  the  DODIN  as required.
2.1.2.  Coordinate with DISA  on  all activities related  to  DISN  Command,  Control, Communications, and Computers and information systems for which DISA has development, execution, review, integration, testing, or support responsibilities.
2.1.3.  Identify  support  requirements  for  DISA  networks,  telecommunications,  and  IT systems, services, and capabilities to the Director, DISA, in accordance with DoDD 5105.19.
~~~~

## R065
Document: afman17-2101  |  chunk 50  |  page 17

Quote (the requirement text to judge):
> Per reference (DODI 8220.02), United States task forces may support civil-military partners in SRDR and civic assistance operations. These operations may include extending IT services to Foreign National First Responders and other International health care organizations and

Chunk 50 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[COMMERCIAL INTERNET SERVICE PROVIDER (ISP) > 3.1. Commercial Internet Service Provider (CISP) Connection]

3.1.1.1.2.  Temporary Facilities/Urgent or Ad Hoc Missions. Provisional commercial connections  installed  to  support  temporary  facilities  or  missions  due  to  DoD employee relocation caused by military construction, natural disaster, or unforeseeable events where the AFIN is not available or would be cost-prohibitive to install due to the temporary nature of the need.
3.1.1.1.3.  Infrastructure  Non-availability.  Interim  commercial  connections  installed to  support  AF  IT  requirements  due  to  loss  of  telecommunication  infrastructure (Outside plant cabling system, communication nodes, etc.) caused by natural disaster, significant equipment refresh, repairs, or unforeseeable events where the AFIN is not available or would be cost- prohibitive to install due to the temporary nature of the need.
3.1.1.1.4.  Stabilization and Reconstruction, Disaster Relief (SRDR), and Humanitarian  and  Civic  Assistance  Operations.  ⟦Per  reference  (DODI  8220.02), United  States  task  forces  may  support  civil-military  partners  in  SRDR  and  civic assistance operations. These operations may include extending IT services to Foreign National  First  Responders  and  other  International  health  care  organizations  and⟧
~~~~

Previous chunk 49:
~~~~text
[COMMERCIAL INTERNET SERVICE PROVIDER (ISP) > 3.1. Commercial Internet Service Provider (CISP) Connection]

3.1.1.  Types. CISP connections do not connect to the AF Information Network infrastructure and  require  authorization  through  the  DoD  and  AF  DISN  waiver  process.  Information Services  (ISs)  that  process,  store  and  transmit  DoD  data  using  a  CISP  connection  must perform categorization in accordance with DoDI 8510.01 tailored appropriately to determine the  set  of  security  controls  to  be  implemented  with  the  approval  of  the  IS's  Authorizing Official (AO).  Tailoring of security controls must take into account the sensitivity of the data being  processed,  stored,  and  transmitted  (e.g.,  controlled  DoD  data,  publically  releasable data) and protection of the supporting IS. The CISP connection cannot be connected directly to the DISN. Use of an approved hardware/software secure tunnel (IPSEC only) such as an AF-  approved,  virtual  private  network  (VPN)  across  a  CISP  circuit  to  connect  to  the DISN/AF  Information  Network  (AFIN)  is  allowed.  Tunneling  classified  data  via  a  CISP requires a DODIN waiver based in DoD Policy. These systems shall not be connected to the base network/NIPRNET with the privileges of '.mil' registered users. CISPs will not be used to host classified systems directly, a CISP connect can only be used to tunnel the classified connection.
~~~~

## R066
Document: DODI 8410.03  |  chunk 6  |  page 7

Quote (the requirement text to judge):
> The DoD CIO, shall provide strategy, policy, oversight, and guidance for NM capability, planning, definition, and implementation across the DoD Information Enterprise and GIG IAW Reference (b).

Chunk 6 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- a.  Provide strategy, policy, oversight, and guidance for NM capability, planning, definition, and implementation across the DoD Information Enterprise and GIG IAW Reference (b).
- b.  In coordination with Under Secretary of Defense for Acquisition, Technology, and Logistics (USD(AT&L)) and the Heads of the DoD Components, develop:
- (1)  End-to-end NM architectures and strategies that support efficient, effective, and secure NM operations in tactical and non-tactical networks and improve interoperability across NM systems.
- (2)  Mission-driven NM metrics for tactical and non-tactical networks and NM systems that enable consistent assessments of DoD network protection and performance.
- (3)  Strategies and architectures for IT resource management capabilities that efficiently and effectively integrate NM and SM systems across doctrine, organization, training, materiel, leadership and education, personnel and facilities (DOTMLPF).
~~~~

Previous chunk 5:
~~~~text
[Enclosures]

1.  References
2.  Responsibilities
3.  Procedures
Glossary
~~~~

## R067
Document: afman17-2101  |  chunk 51  |  page 18

Quote (the requirement text to judge):
> these connections will comply with all DoD cybersecurity policies.

Chunk 51 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[COMMERCIAL INTERNET SERVICE PROVIDER (ISP) > 3.1. Commercial Internet Service Provider (CISP) Connection]

assistance  organizations.  To  ensure  security  of  the  AFIN,  these  connections  will normally  be  commercial  in  nature  and  include  Wireless  Access  Points  (WAPs), SATCOM, links, or terrestrial connections on Foreign telecommunication infrastructure for emergency response trucks/trailers and mobile emergency operations centers.
3.1.1.1.5.  Recruiting.  Due  to  the  location  (e.g.,  strip  malls,  commercial  buildings), number of users (5 - 7), and mobile quality of recruiting stations (recruit from the youth population), it is cost prohibitive to procure anything  but  commercial connections for recruiting offices;  however, ⟦these connections will comply with all DoD cybersecurity policies.⟧
~~~~

Previous chunk 50:
~~~~text
[COMMERCIAL INTERNET SERVICE PROVIDER (ISP) > 3.1. Commercial Internet Service Provider (CISP) Connection]

3.1.1.1.2.  Temporary Facilities/Urgent or Ad Hoc Missions. Provisional commercial connections  installed  to  support  temporary  facilities  or  missions  due  to  DoD employee relocation caused by military construction, natural disaster, or unforeseeable events where the AFIN is not available or would be cost-prohibitive to install due to the temporary nature of the need.
3.1.1.1.3.  Infrastructure  Non-availability.  Interim  commercial  connections  installed to  support  AF  IT  requirements  due  to  loss  of  telecommunication  infrastructure (Outside plant cabling system, communication nodes, etc.) caused by natural disaster, significant equipment refresh, repairs, or unforeseeable events where the AFIN is not available or would be cost- prohibitive to install due to the temporary nature of the need.
3.1.1.1.4.  Stabilization and Reconstruction, Disaster Relief (SRDR), and Humanitarian  and  Civic  Assistance  Operations.  Per  reference  (DODI  8220.02), United  States  task  forces  may  support  civil-military  partners  in  SRDR  and  civic assistance operations. These operations may include extending IT services to Foreign National  First  Responders  and  other  International  health  care  organizations  and
~~~~

## R068
Document: DODI 8410.03  |  chunk 13  |  page 9

Quote (the requirement text to judge):
> The USD(AT&L) shall implement automated CM and PBNM capabilities and standards in new or modified NM systems, including but not specifically limited to determining architectures and technical approaches for: Contingency-based configuration changes that will satisfy a typical joint operation, including potential coalition partners or similar.

Chunk 13 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[3.  USD(AT&L).  The USD(AT&L) shall:]

- a.  Provide coordination and support to ensure that any policies, guidance, or requirements proposed by the DoD CIO regarding SM and NM requirements impacting access to defense networks and vendor facing applications by members of the Defense Industrial Base (DIB) will not place any undue burdens on industry.
- b.  Prepare and coordinate acquisition and contracting policy, procedures, and regulation among DIB members and Federal partners necessary to implement this Instruction.
- c.  Coordinate with DIB members supplying  materiel and services, to ensure an executable and affordable migration strategy to meet SM and NM requirements resulting from the implementation of  this Instruction.
- d.  Implement automated CM and PBNM capabilities and standards in new or modified NM systems, including but not specifically limited to determining architectures and technical approaches for:
- (1)  Network traffic bandwidth prioritization.
- (2)  Contingency-based configuration changes that will satisfy a typical joint operation, including potential coalition partners or similar.
- (3)  Implementing automated configuration change technologies.
- (4)  Determining standard methods for human override of automated configuration changes.
~~~~

Previous chunk 12:
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- j.  Develop and promulgate DoD-wide standards and guidelines for use of NM protocols (such as SNMP or network configuration protocol) for communication of NM information between NM systems and their managed network elements (NEs).
- k.  Develop, in coordination with the Commander, U.S. Strategic Command (USSTRATCOM), technical guidance for integrating and correlating NM and SM capabilities to enable near real-time end-to-end network SA throughout the GIG.
- l.  Support the USD(AT&L) in reviewing and studying automated CM and PBNM capabilities and standards.
- m.  Develop and promulgate technical guidance and architectures for developing and implementing automated CM and PBNM systems.
- n.  Establish and maintain a central repository of SLAs.
~~~~

## R069
Document: DODI 8410.03  |  chunk 36  |  page 19

Quote (the requirement text to judge):
> Data exchanges between NM systems shall be encrypted per DISA Security Technical Implementation Guides Network Infrastructure (Reference (ab)) and shall be processed and protected at the appropriate classification level.

Chunk 36 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[5.  NM SECURITY]

- a.  ⟦Data exchanges between NM systems shall be encrypted per DISA Security Technical Implementation Guides Network Infrastructure (Reference (ab)) and shall be processed and protected at the appropriate classification level.⟧
- b.  Management information obtained from NEs shall be classified, stored, processed, and shared IAW the USSTRATCOM GIG NetOps Security Classification Guide (Reference (ac)) and other applicable classification guides.  NM data that provides sensitive operational status of the network or the status of the network's ability to support real-world operations shall be protected as sensitive information (minimum) or at an appropriate higher classification level based on the classification of the network it is derived from.
~~~~

Previous chunk 35:
~~~~text
[4.  SLAs]

- (4)  Mean time to repair failures in network equipment or connectivity.
- (5)  Throughput of a given network node, by traffic type.
- (6)  Percentage of available bandwidth consumed on a given link, by traffic type.
- (7)  Fault status, by node priority.
- (8)  Packet error rate and bit error rate (average and standard deviation) through a given network node.
- (9)  Quality of service requirements for NM and control plane traffic.
~~~~

## R070
Document: afman17-2101  |  chunk 35  |  page 13

Quote (the requirement text to judge):
> Ensure all Defense Service Network (DSN) dedicated precedence service requests are approved in accordance with CJCSI 6211.02.

Chunk 35 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.2.2.3.  Prepare orders in accordance with DISAC 310-130-1 and DISA Provisioning Notices.
- 2.8.2.3.  Identify  and  obtain  special  circuit  considerations  (i.e.  diversity,  avoidance, redundancy, and survivability) to meet mission specifications.
- 2.8.2.4.  Identify proper TSP level (DISAC 310-130-4 and DISAC 310-130-1).
- 2.8.2.5.  Ensure  TS/SCI  connections  (TS/SCI  IP  DATA,  NSANet)  are  submitted  for validation and approval to the appropriate A2 designated office.
- 2.8.2.6.  ⟦Ensure  all  Defense  Service  Network  (DSN)  dedicated  precedence  service requests are approved in accordance with CJCSI 6211.02.⟧
- 2.8.2.7.  Manage  expired/expiring  CSA    program  to  ensure  commercial  circuits  and services  are  re-awarded  or  discontinued  in  accordance  with  DISA    Global  Contract Reaward Actions.
~~~~

Previous chunk 34:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.1.  MAJCOM level CMO workload responsibilities were consolidated under the AF LHC Flight at 38 CYRS/SCC.
- 2.8.2.  All  CMO  not  part  of  the  MAJCOM  CMO's  consolidation  effort  retain  their  CMO responsibilities to:
- 2.8.2.1.  Provision,  track,  and  manage  LHC  circuits  and  service  throughout  their  life cycle.
- 2.8.2.2.  Register and obtain appropriate role assignments in DISA StoreFront provisioning tool and AF TCOSS for their respective organizations.  All CMO's will:
- 2.8.2.2.1.  Prepare, review, validate, approve, and/or reject Service Requests in DISA StoreFront for long-haul circuits, services, and equipment submitted by subordinate organizations.
- 2.8.2.2.2.  Assist  and  guide  subordinate  organizations  on  LHC  management  which include  (but  not  limited  to  user  account  registration  in  DISA  StoreFront  and  AF TCOSS required to manage LHC circuits, services and funding.
~~~~

## R071
Document: afman17-2101  |  chunk 44  |  page 15

Quote (the requirement text to judge):
> AFO's will approve and/or disapprove DISA StoreFront Service Requests

Chunk 44 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[ROLES AND RESPONSIBILITIES > 2.10. Authorized Funding Official (AFO) for organizations who fund and own DISN AF LHC circuits and/or services must: > 2.10.1.1.  AFO's will:]

- 2.10.1.1.1.  Update at the start of each fiscal  year the funding PDC with a certified MORD number, Line of Accounting (LOA), and Customer Account Information in TIBI  (T-0)
- 2.10.1.1.2.  Approve and/or disapprove DISA StoreFront Service Requests.
- 2.10.1.1.3.  Reconcile LHC  invoices  for all  DISN  ordered  telecommunications equipment and services, CSA's and/or other acquisition documents before authorizing payment. (T-0)
- 2.10.1.1.4.  Submit  PDC  requests  to  38  CYRS/SCC  Financial  Analyst  point  of contact.
- 2.10.1.1.5.  Validate  OSD/DITCO  Quarterly  Statistical  Sampling  invoice  in  TIBI when requested by 38 CYRS/SCC Financial Analyst. (T-0)
~~~~

Previous chunk 43:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.10. Authorized Funding Official (AFO) for organizations who fund and own DISN AF LHC circuits and/or services must:]

- 2.10.1.  Appoint an AFO in writing to their Headquarters level LAFO. An AFO is a civilian or military personnel at unit level responsible for approving and managing LHC funding for circuits and services. AFOs can only request access to their assigned PDC's.
~~~~

## R072
Document: afman17-2101  |  chunk 34  |  page 12

Quote (the requirement text to judge):
> Assist and guide subordinate organizations on LHC management which include (but not limited to user account registration in DISA StoreFront and AF TCOSS required to manage LHC circuits, services and funding.

Chunk 34 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.1.  MAJCOM level CMO workload responsibilities were consolidated under the AF LHC Flight at 38 CYRS/SCC.
- 2.8.2.  All  CMO  not  part  of  the  MAJCOM  CMO's  consolidation  effort  retain  their  CMO responsibilities to:
- 2.8.2.1.  Provision,  track,  and  manage  LHC  circuits  and  service  throughout  their  life cycle.
- 2.8.2.2.  Register and obtain appropriate role assignments in DISA StoreFront provisioning tool and AF TCOSS for their respective organizations.  All CMO's will:
- 2.8.2.2.1.  Prepare, review, validate, approve, and/or reject Service Requests in DISA StoreFront for long-haul circuits, services, and equipment submitted by subordinate organizations.
- 2.8.2.2.2.  ⟦Assist  and  guide  subordinate  organizations  on  LHC  management  which include  (but  not  limited  to  user  account  registration  in  DISA  StoreFront  and  AF TCOSS required to manage LHC circuits, services and funding.⟧
~~~~

Previous chunk 33:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.7. All Air Force Centers, Agencies, and Other Key Stakeholder will:]

2.7.1.  Validate  centrally  funded  SBU  IP  DATA  and  SECRET  IP  DATA  transport connections,  and  Internet  Protocol  addressing,  on-site  assistance  requests  and  systems configuration. This responsibility includes conducting Review & Revalidation on connections every 2 years.
- 2.7.1.1.  Submit requests to terminate unused AF funded SBU IP DATA and SECRET IP DATA connections when no longer required.
- 2.7.2.  Program Management Offices:
- 2.7.2.1.  Ensure  networked systems that use  LHC transport are bandwidth-efficient and include implementation of software and/or hardware compression/acceleration technologies where possible.
- 2.7.2.2.  Determine system LHC bandwidth requirements by base/site and submit circuit bandwidth requirements according to the AF LHC Requirements Process.
- 2.7.2.3.  Review/revalidate bandwidth requirements prior to initial fielding.
- 2.7.2.4.  Program  for  DISN  LHC  costs  as  part  of  overall  lifecycle  costs  and  Program Objective Memorandum.
~~~~

## R073
Document: afman17-2101  |  chunk 39  |  page 14

Quote (the requirement text to judge):
> Coordinate and schedule power outages (i.e. base Civil Engineering) with DISA, Major Commands, Cyber Operations Flight/690 Network Support Squadron, and affected AF customers that will impact communication facilities, rooms, racks, and equipment.

Chunk 39 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.3.7.  Review and revalidate all requirements for base telecommunications equipment and services. (T-0)
- 2.8.3.7.1.  Terminate services that are uneconomical or no longer needed in accordance with CJCSI 6211.02. (T-0)
- 2.8.3.8.  Coordinate  Authorized  Service  Interruptions  (ASIs)  with  Subordinate  units, affected AF customers and tenant organizations. Submit concurrence or non- concurrence to the base Communications Focal Point for SBU I DATA,  SECRET IP DATA, and 24 AF designated mission  critical circuits.  All other ASI's are coordinated directly with DISA and guidance in DISAC 310-55-1, Status Reporting. (T-3)
- 2.8.3.9.  ⟦Coordinate and schedule power outages (i.e. base Civil Engineering) with DISA, Major Commands,  Cyber  Operations  Flight/690   Network    Support  Squadron,    and affected  AF  customers  that  will   impact   communication facilities, rooms, racks, and equipment.⟧
~~~~

Previous chunk 38:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.3.3.3.  Circuit Layout Records which is a drawing that depicts the physical layout of trunks and circuits.
- 2.8.3.3.4.  Master Station Log which is a record of information on significant events occurring within the area of assigned responsibility.
- 2.8.3.4.  Track facility, link, trunk, circuit, channel, equipment outages, and HAZCONs within the activity area of responsibility. Outage and restoration records are maintained in accordance with DISAC 310-70-1 and DISAC 310-55-1.
- 2.8.3.5.  Establish a trend analysis program on all circuits, trunks for which they are the Circuit Control Office (CCO) or servicing activity, and on all circuits and trunks which terminate at their station in accordance with DISAC 310-70-1 and DISAC 310-130-2.
- 2.8.3.6.  Maintain an inventory of all base telecommunications equipment and services in accordance with CJCSI 6211.02. (T-0)
~~~~

## R074
Document: afman17-2101  |  chunk 27  |  page 10

Quote (the requirement text to judge):
> Appoint a LAFO and alternate and forward appointment letter to 38 CYRS/SCC.

Chunk 27 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[ROLES AND RESPONSIBILITIES > 2.4. Major Commands, Management Headquarters (MHQ), AF level Organizations will:]

2.4.1.  Execute LAFO duties as detailed in Chapter 2, paragraph 2.11 of this AFMAN.
- 2.4.2.  Appoint a Long Haul Comm point of Contact (POC) for circuit management and LHC related  issues  and  forward  appointment  letter  to  AF  Long  Haul  Communication  Flight,  38 Cyberspace Readiness Squadron/SCC. (T-3)
- 2.4.3.  ⟦Appoint a LAFO and alternate and forward appointment letter to 38 CYRS/SCC.⟧ If the LAFO and alternate are identified as the LHC POC state that in the LAFO appointment letter.
Note: AF-level FOAs and DRUs that do not have LHC requirements (circuits and services) do NOT need to appoint a LHC POC or LAFO and alternate.
- 2.4.4.  Appoint  one  or  more  Telecommunications  Service  Priority  (TSP)  NS/EP  Invoking Officials in writing IAW NCS Directive 3-1 Telecommunications Service Priority.
~~~~

Previous chunk 26:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.3. AF  Long  Haul  Communications  Flight,  38th  Cyberspace  Readiness  Squadron/SCC (38 CYRS/SCC). The AF LHC Flight is the Air Force's DISN LHC Program manager who:]

- 2.3.18.  Represents the AF with government and DOD procurement actions involving longhaul requirements and participates in contract evaluation panels.
- 2.3.19.  Participates in working groups internal and external to AF, providing LHC technical and/or procedure SME recommendations and guidance.
- 2.3.20.  Coordinates  with  all  appropriate  organizations  (DISA,  the  AF  customers/mission system  managers,  sister  services,  COCOMs  and  other  DOD  Agencies)  regarding  contract transitions which affect circuits, equipment, and services.
- 2.3.21.  Forwards National Security Emergency Preparedness (NS/EP) appointment letters to Department of Homeland Security TSP Program Office. ( tsp@hq.dhs.gov )
- 2.3.22.  Manages the expired/expiring Communications Service Authorization (CSA) program to  ensure commercial  circuits  and  services  are  re-awarded  or  discontinued  IAW DISA Global Contract Re-award Actions Tactics, Techniques, and Procedures.
~~~~

## R075
Document: DODI 8410.03  |  chunk 2  |  page 2

Quote (the requirement text to judge):
> All NM systems shall be capable of distributed network control and facilitate net-centric sharing of network configuration, status, security, performance, utilization, and mission impact data with authorized users in accordance with (IAW) section 2 of Enclosure 3 of this Instruction.

Chunk 2 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[2.  APPLICABILITY.  This Instruction:]

- c.  Shall not alter or supersede the existing authorities and policies of the Director of National Intelligence regarding the protection of sensitive compartmented information (SCI) and special access programs (SAP) for intelligence as directed by Executive Order 12333 (Reference (e)) and other laws and regulations.  The application of the provisions and procedures of this Instruction to SCI or other SAP for intelligence information systems is encouraged where they may complement or discuss areas not otherwise specifically addressed.
3.  DEFINITIONS.  See Glossary.
4.  POLICY.  It is DoD policy that:
- a.  ⟦All NM systems shall be capable of distributed network control and facilitate net-centric sharing of network configuration, status, security, performance, utilization, and mission impact data with authorized users in accordance with (IAW) section 2 of Enclosure 3 of this Instruction.⟧
- b.  Systems that use Simple Network Management Protocol (SNMP) shall use the latest version as the target protocol version IAW section 3 of Enclosure 3.
~~~~

Previous chunk 1:
~~~~text
[2.  APPLICABILITY.  This Instruction:]

- a.  Applies to OSD, the Military Departments, the Office of the Chairman of the Joint Chiefs of Staff (CJCS) and the Joint Staff, the Combatant Commands, the Office of the Inspector General of the Department of Defense, the Defense Agencies, DoD Field Activities, and all other organizational entities within the DoD (hereinafter referred to collectively as the 'DoD Components').
- b.  Applies to all DoD NM systems and associated technology, processes, personnel, and organizations that receive, process, store, display, or transmit DoD information, regardless of classification or sensitivity, to include NM systems operated by a contractor or other entity on behalf of DoD and any NM system interfaces to DoD mission partners.
NUMBER 8410.03 August 29, 2012 Incorporating Change 1, July 19, 2017
DoD CIO
~~~~

## R076
Document: DODI 8410.03  |  chunk 6  |  page 7

Quote (the requirement text to judge):
> In coordination with Under Secretary of Defense for Acquisition, Technology, and Logistics (USD(AT&L)) and the Heads of the DoD Components, develop End-to-end NM architectures and strategies that support efficient, effective, and secure NM operations in tactical and non-tactical networks and improve interoperability across NM systems.

Chunk 6 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- a.  Provide strategy, policy, oversight, and guidance for NM capability, planning, definition, and implementation across the DoD Information Enterprise and GIG IAW Reference (b).
- b.  In coordination with Under Secretary of Defense for Acquisition, Technology, and Logistics (USD(AT&L)) and the Heads of the DoD Components, develop:
- (1)  End-to-end NM architectures and strategies that support efficient, effective, and secure NM operations in tactical and non-tactical networks and improve interoperability across NM systems.
- (2)  Mission-driven NM metrics for tactical and non-tactical networks and NM systems that enable consistent assessments of DoD network protection and performance.
- (3)  Strategies and architectures for IT resource management capabilities that efficiently and effectively integrate NM and SM systems across doctrine, organization, training, materiel, leadership and education, personnel and facilities (DOTMLPF).
~~~~

Previous chunk 5:
~~~~text
[Enclosures]

1.  References
2.  Responsibilities
3.  Procedures
Glossary
~~~~

## R077
Document: afman17-2101  |  chunk 59  |  page 20

Quote (the requirement text to judge):
> Register the CISP in the Systems/Networks Approval Process (SNAP) database.

Chunk 59 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[COMMERCIAL INTERNET SERVICE PROVIDER (ISP) > 3.1. Commercial Internet Service Provider (CISP) Connection]

3.1.1.2.5.3.  AETC  Recruit,  Training,  and  Education  Action  Officer  (RT&E) developed  an  in-house  DODIN  Waiver  Exemption  Process  that  precludes  the need to go through the DODIN Waiver process if unit meet certain criteria similar to quality of life (e.g. education/training centric, no For Official Use Only data, no malware).
3.1.1.2.6.  Geographically Separated Unit (GSU). The GSU owning Major Command or  Management  Headquarters  will  fund  any  network  circuit(s)  required  for  GSU connectivity.  GSUs  will  comply  with  all  policies  and  directives  of  servicing  AFIN Operations activity including Comm Focal Point supporting their network circuit.
3.1.1.3.  Requirements. Devices using the CISP must be physically or logically separated from the AFIN network and comply with applicable Security Technical Implementation Guides (STIG), Security Recommendation Guides (SRG), and other DoD cyber security policies. ⟦Register the CISP in the Systems/Networks Approval Process (SNAP) database.⟧
~~~~

Previous chunk 58:
~~~~text
[COMMERCIAL INTERNET SERVICE PROVIDER (ISP) > 3.1. Commercial Internet Service Provider (CISP) Connection]

3.1.1.2.5.  Headquarters Air Education and Training Command (HQ AETC) and the United  States  AF  Academy  (USAFA).  HQ  AETC  and  USAFA  require  academic networks that provide students, faculty, and staff IT services that are not available on the AFNET (i.e., conduct research and scientific collaborations). Consequently, HQ AETC and USAFA are authorized to operate networks specifically  designed  to  IT enable their education and training missions.
3.1.1.2.5.1.  Authorizing  Official  Approval  is  required  for  AETC  and  USAFA operated education and training academic networks.
3.1.1.2.5.2.  AETC and USAFA  operated  education and training academic networks  are  exempt  from  the  DoD  Information  Network  (DODIN)  Waiver process if they do not process, store, or transmit sensitive information.
~~~~

## R078
Document: NIST.SP.800-125  |  chunk 94  |  page 29

Quote (the requirement text to judge):
> ensure that policies are updated accordingly as needed.

Chunk 94 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[5. Secure Virtualization Planning and Deployment > 5.1 Initiation]

Every year, there are many changes in virtualization capabilities, the security controls available to organizations, the types of threats against different types of virtualization, and so on. Therefore, organizations should periodically reassess their policies for virtualization. Organizations should also be aware of the emergence of new types of virtualization solutions and of major changes to existing virtualization technologies, and ⟦ensure that policies are updated accordingly as needed.⟧
~~~~

Previous chunk 93:
~~~~text
[5. Secure Virtualization Planning and Deployment > 5.1 Initiation]

Organizations should be aware of how their use of virtualization may affect the security categorization of the physical system. The security categories associated with Federal information system based on three security objectives: confidentiality, integrity and availability. These security categories are described in NIST FIPS 199, Standards for Security Categorization of Federal Information and Information Systems. The security categorization of a particular information system depends on the potential impact associated with a loss of confidentiality, integrity or availability. If a system hosts guest OSs with different impact levels, the system should be secured in accordance with the highest of those levels. The organization's virtualization security policy should define how combining multiple guest OSs on a single system affects the system's security requirements, both positively and negatively, and which combinations of guest OSs are permitted or prohibited. Organizations may also choose to reduce risk by prohibiting combinations that include resources accessing particular types of information, such as highly sensitive personally identifiable information (PII). 3
~~~~

## R079
Document: afman17-2101  |  chunk 54  |  page 18

Quote (the requirement text to judge):
> At a minimum, protect financial transactions conducted via the internet (e.g. Defense Travel System, transient housing or Morale Welfare & Recreation (MWR) hotels, Defense Exchange Commissary Agency (DECA), etc.) in accordance with Payment Card Industry Data Security Standards (PCI DSS) using Federal Information Processing Standard (FIPS) 140-2 encryption.

Chunk 54 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[COMMERCIAL INTERNET SERVICE PROVIDER (ISP) > 3.1. Commercial Internet Service Provider (CISP) Connection]

3.1.1.1.8.  Payment  Card  Industry.  AF  organizations  processing  Automatic  Teller Machine (ATM) or Point of Sale (POS) transactions must connect to civilian financial institutions  and  credit  card  companies  to  process  these  requests.  ⟦At  a  minimum, protect financial transactions conducted via the internet (e.g. Defense Travel System, transient housing or Morale Welfare & Recreation (MWR) hotels, Defense Exchange Commissary Agency (DECA), etc.) in accordance with Payment Card Industry Data Security Standards (PCI DSS) using Federal Information Processing Standard (FIPS) 140-2 encryption.⟧
3.1.1.2.  Publically  releasable  DoD  data  can  be  authorized  over  CISP  based  upon  the following  use  cases  conditions.  The  Authorizing  Official  will  tailor  the  appropriate security controls for the supporting IS in accordance with DODI 8510.01.
~~~~

Previous chunk 53:
~~~~text
[COMMERCIAL INTERNET SERVICE PROVIDER (ISP) > 3.1. Commercial Internet Service Provider (CISP) Connection]

3.1.1.1.7.  Civil  Authority  Databases.    Connections  to  data  repositories  such  as National Crime Information Center (NCIC), Terrorist Screening Database, Department  of  Homeland  Security  database  (E-Verify  and  U.S.  VISIT),  and  other authoritative  data  sources  to  vet  the  claimed  identity  and  to  determine  fitness  to access an Installation or site to remain in compliance with Directive-Type Memorandum  (DTM)  09-012,  Interim  Policy  Guidance  for  DoD  Physical  Access Control. Connections to global crime databases for criminal justice information (CJI) retrieved through DoD Identity Management Capability Enterprise Services Application (IMESA)  used  and  acted upon  in accordance with existing law enforcement procedures.
~~~~

## R080
Document: afman17-2101  |  chunk 39  |  page 14

Quote (the requirement text to judge):
> Coordinate Authorized Service Interruptions (ASIs) with Subordinate units, affected AF customers and tenant organizations.

Chunk 39 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.3.7.  Review and revalidate all requirements for base telecommunications equipment and services. (T-0)
- 2.8.3.7.1.  Terminate services that are uneconomical or no longer needed in accordance with CJCSI 6211.02. (T-0)
- 2.8.3.8.  ⟦Coordinate  Authorized  Service  Interruptions  (ASIs)  with  Subordinate  units, affected AF customers and tenant organizations.⟧ Submit concurrence or non- concurrence to the base Communications Focal Point for SBU I DATA,  SECRET IP DATA, and 24 AF designated mission  critical circuits.  All other ASI's are coordinated directly with DISA and guidance in DISAC 310-55-1, Status Reporting. (T-3)
- 2.8.3.9.  Coordinate and schedule power outages (i.e. base Civil Engineering) with DISA, Major Commands,  Cyber  Operations  Flight/690   Network    Support  Squadron,    and affected  AF  customers  that  will   impact   communication facilities, rooms, racks, and equipment.
~~~~

Previous chunk 38:
~~~~text
[ROLES AND RESPONSIBILITIES > 2.8. Functional LHC Circuit Management Office (CMO) Responsibilities.]

- 2.8.3.3.3.  Circuit Layout Records which is a drawing that depicts the physical layout of trunks and circuits.
- 2.8.3.3.4.  Master Station Log which is a record of information on significant events occurring within the area of assigned responsibility.
- 2.8.3.4.  Track facility, link, trunk, circuit, channel, equipment outages, and HAZCONs within the activity area of responsibility. Outage and restoration records are maintained in accordance with DISAC 310-70-1 and DISAC 310-55-1.
- 2.8.3.5.  Establish a trend analysis program on all circuits, trunks for which they are the Circuit Control Office (CCO) or servicing activity, and on all circuits and trunks which terminate at their station in accordance with DISAC 310-70-1 and DISAC 310-130-2.
- 2.8.3.6.  Maintain an inventory of all base telecommunications equipment and services in accordance with CJCSI 6211.02. (T-0)
~~~~

## R081
Document: DODI 8410.03  |  chunk 30  |  page 17

Quote (the requirement text to judge):
> The community strings shall be modified from default settings - default 'public' and 'private' strings shall not be utilized.

Chunk 30 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[3.  NM USE OF SNMP]

- (7)  ⟦The community strings shall be modified from default settings - default 'public' and 'private' strings shall not be utilized.⟧
- (8)  Periodic SNMP polling should be done with a read-only community string, and readwrite strings should be used only for write operations, based on the capabilities of the NM system.
- (9)  Unauthorized attempts to access SNMP managed NE shall be aggressively monitored and reported.
- (10)  Device, account, and application passwords will not be passed over SNMP until the transition to the latest version is accomplished.
- g.  Access control lists shall be implemented on SNMP managed NEs, where possible, to restrict access to only authorized NM operators and NM systems.
~~~~

Previous chunk 29:
~~~~text
[3.  NM USE OF SNMP]

- (1)  NEs requiring SNMP management shall be properly configured with appropriate read-only and read-write community names (commonly referred to as 'community strings').
- (2)  Read-only and read-write SNMP community strings for a managed device shall be different.
- (3)  Where possible, a different string (or strings) shall be utilized for each NE, or at minimum for each area of the network being managed.  For instance, if an authorized user requests access to information about DISN, they could be given a read-only community string and a list of devices that it can be used to access.  In addition to enabling access, this approach allows network managers to quickly and easily isolate portions of the network and serves to keep the number of required community strings to a manageable level.
- (4)  SNMP community strings shall be safeguarded and protected against compromise at the level of the operational network.
- (5)  SNMP community strings shall meet the minimum password length and composition requirements required by applicable security controls.
- (6)  The community strings and management passwords shall be changed at least annually and when there is a possibility that one has been compromised.
~~~~

## R082
Document: afman17-2101  |  chunk 7  |  page 4

Quote (the requirement text to judge):
> DOD Chief Information Officer (CIO) policy mandates all DOD Service Components and Agencies provision and fund the shared DOD network and services from DISA to promote Joint interoperability.

Chunk 7 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[AF LONG-HAUL COMMUNICATIONS (AF LHC) MANAGEMENT]

1.1.2.1.  ⟦DOD  Chief  Information  Officer  (CIO)  policy  mandates  all  DOD  Service Components  and  Agencies  provision  and  fund  the  shared  DOD  network  and  services from DISA to promote Joint interoperability.⟧
- 1.1.3.  The AF Information Network (AFIN) is the AF managed segment of the DoD network known as the DODIN and its subcomponent, that is called the DISN.
1.1.3.1.  The  DISN  is  comprised  of  Non-Secure  Internet  Protocol  Router  Network (NIPRNET) also referred to as "Sensitive but Unclassified IP Data" and Secure Internet Protocol Router Network (SIPRNET) also referred to as "Secret IP Data".
- 1.1.3.2.  The  AF  Network  (AFNET)  is  the  AF's  underlying  unclassified  network  that enables AF operational capabilities and lines of business.
1.1.3.3.  AFNET-S  is  the  secret  level  AFNET  also  known  as  the  classified  network (Secret) that enables AF operational capabilities and lines of business.
~~~~

Previous chunk 6:
~~~~text
[AF LONG-HAUL COMMUNICATIONS (AF LHC) MANAGEMENT]

1.1. Overview. Long  Haul  Telecommunications  is  all  general  and  special  purpose  longdistance  telecommunications,  facilities  and  services  (including  commercial  satellite  services, terminal equipment and local circuitry  supporting the long-haul service  ) to or from the base, post camp or station switch and/or main distribution frame (except for trunk lines to the firstserving commercial central office for local communications services).
1.1.1.  The  AF  centrally  provisions,  manages  and  funds  the  AF  enterprise  Long  Haul Communications  transport  portion  of  the  DOD  network  and  services  called  the  Defense Information  Systems  Network  (DISN)  and  the  AF  segment  called  the  AF  Information Networks (AFIN) which uses the DISN for transport.
1.1.2.  DOD policy assigns Defense Information Systems Agency (DISA) the responsibility to provide end-to-end DOD Information Network (DODIN) infrastructure and to provision, manage and sustain DISN transport, services, facilities, and equipment in direct support of DOD missions, the Joint warfighter and AF operational readiness.
~~~~

## R083
Document: DODI 8410.03  |  chunk 12  |  page 9

Quote (the requirement text to judge):
> The DoD CIO, shall develop and promulgate DoD-wide standards and guidelines for use of NM protocols (such as SNMP or network configuration protocol) for communication of NM information between NM systems and their managed network elements (NEs).

Chunk 12 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- j.  Develop and promulgate DoD-wide standards and guidelines for use of NM protocols (such as SNMP or network configuration protocol) for communication of NM information between NM systems and their managed network elements (NEs).
- k.  Develop, in coordination with the Commander, U.S. Strategic Command (USSTRATCOM), technical guidance for integrating and correlating NM and SM capabilities to enable near real-time end-to-end network SA throughout the GIG.
- l.  Support the USD(AT&L) in reviewing and studying automated CM and PBNM capabilities and standards.
- m.  Develop and promulgate technical guidance and architectures for developing and implementing automated CM and PBNM systems.
- n.  Establish and maintain a central repository of SLAs.
~~~~

Previous chunk 11:
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- g.  Create, manage, and maintain a common repository based upon security classifications within the MDR for all data-exchange schemas and SNMP MIBs used by NM systems, including supporting documentation and interface characteristics and specifications.
- h.  Participate in applicable standards bodies and organizations to advocate for and aid in developing standards, protocols, and mechanisms for translating NM information from current formats (e.g., SNMP) to ones that facilitate net-centric information sharing (e.g., extensible markup language).
- i.  Develop, in coordination with the DoD Components, a GIG technical profile (GTP) to define the interface specifications for exchanging data between NM systems.
~~~~

## R084
Document: DODI 8410.03  |  chunk 13  |  page 9

Quote (the requirement text to judge):
> The USD(AT&L) shall implement automated CM and PBNM capabilities and standards in new or modified NM systems, including but not specifically limited to determining architectures and technical approaches for: Network traffic bandwidth prioritization.

Chunk 13 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[3.  USD(AT&L).  The USD(AT&L) shall:]

- a.  Provide coordination and support to ensure that any policies, guidance, or requirements proposed by the DoD CIO regarding SM and NM requirements impacting access to defense networks and vendor facing applications by members of the Defense Industrial Base (DIB) will not place any undue burdens on industry.
- b.  Prepare and coordinate acquisition and contracting policy, procedures, and regulation among DIB members and Federal partners necessary to implement this Instruction.
- c.  Coordinate with DIB members supplying  materiel and services, to ensure an executable and affordable migration strategy to meet SM and NM requirements resulting from the implementation of  this Instruction.
- d.  Implement automated CM and PBNM capabilities and standards in new or modified NM systems, including but not specifically limited to determining architectures and technical approaches for:
- (1)  Network traffic bandwidth prioritization.
- (2)  Contingency-based configuration changes that will satisfy a typical joint operation, including potential coalition partners or similar.
- (3)  Implementing automated configuration change technologies.
- (4)  Determining standard methods for human override of automated configuration changes.
~~~~

Previous chunk 12:
~~~~text
[1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:]

- j.  Develop and promulgate DoD-wide standards and guidelines for use of NM protocols (such as SNMP or network configuration protocol) for communication of NM information between NM systems and their managed network elements (NEs).
- k.  Develop, in coordination with the Commander, U.S. Strategic Command (USSTRATCOM), technical guidance for integrating and correlating NM and SM capabilities to enable near real-time end-to-end network SA throughout the GIG.
- l.  Support the USD(AT&L) in reviewing and studying automated CM and PBNM capabilities and standards.
- m.  Develop and promulgate technical guidance and architectures for developing and implementing automated CM and PBNM systems.
- n.  Establish and maintain a central repository of SLAs.
~~~~

## R085
Document: DODI 8410.03  |  chunk 38  |  page 20

Quote (the requirement text to judge):
> common NM standards are required to support spectrum-dependent systems and tactical edge NEs.

Chunk 38 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[5.  NM SECURITY]

6.  NM STANDARDS AND SCHEMAS FOR TACTICAL EDGE NE.  To support end-to-end SA and NM system reporting criteria, common NM standards are required to support spectrumdependent systems and tactical edge NEs.
- a.  In consideration of tactical edge NM requirements, the DoD Components with DISA support shall jointly establish NM standards for tactical edge NEs.  The standards shall be maintained by DISA and incorporated into the baseline schemas for NM.  These standards shall consider the unique properties of tactical networking, including but not limited to:
- (1)  The ad-hoc nature of such networks.
- (2)  The requirement for NEs to connect and disconnect at random due to mobility-related constraints.
- (3)  The often limited bandwidth available.
- (4)  Operational requirements to remain in a non-transmitting state for extended periods of time.
- b.  As requested, DISA shall support program managers, in the incorporation of these standards into new or existing programs of record.
~~~~

Previous chunk 37:
~~~~text
[5.  NM SECURITY]

- c.  NM system operator and supervisory positions (e.g., system administrators, network managers and controllers, router and switch administrators, managers and controllers) performing NM IA functions as defined in DoD 8570.01-M (Reference (ad)) shall be designated IA Technical Category Level 2 and IA Management Category Level 2 positions and as critical sensitive positions as defined by DoD 5200.2-R (Reference (ae)), and military, government civilian, and contractor personnel filling them shall meet all required background checks, training, and certification requirements prior to assuming their duties.
- d.  Access to NM systems shall be authorized by the appropriate unit level commander responsible for the NM system.  Only those users with proper credentials and access authorizations will be granted access to NM systems.  NM system users shall comply with the applicable cybersecurity training and certification requirements IAW Reference (ad).
- e.  NM functions are critical within the network infrastructure.  Accordingly, supply chain risk management shall be applied to the acquisition of NM functionality IAW DoDI 5200.44 (Reference (af)) and DoDI 5200.39 (Reference (ag)).
~~~~

## R086
Document: NIST.SP.800-125  |  chunk 10  |  page 7

Quote (the requirement text to judge):
> access to the virtualization management system should be restricted to authorized administrators only

Chunk 10 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[Restrict and protect administrator access to the virtualization solution.]

The security of the entire virtual infrastructure relies on the security of the virtualization management system that controls the hypervisor and allows the operator to start guest OSs, create new guest OS images, and perform other administrative actions. Because of the security implications of these actions, ⟦access to the virtualization management system should be restricted to authorized administrators only⟧. Some virtualization products offer multiple ways to manage hypervisors, so organizations should secure each management interface, whether locally or remotely accessible. For remote administration, the confidentiality of communications should be protected, such as through use of FIPS-approved cryptographic algorithms and modules.
~~~~

Previous chunk 9:
~~~~text
[Secure all elements of a full virtualization solution and maintain their security.]

The security of a full virtualization solution is heavily dependent on the individual security of each of its components, from the hypervisor and host OS (if applicable) to guest OSs, applications, and storage. Organizations should secure all of these elements and maintain their security based on sound security practices, such as keeping software up-to-date with security patches, using secure configuration baselines, and using host-based firewalls, antivirus software, or other appropriate mechanisms to detect and stop attacks. In general, organizations should have the same security controls in place for virtualized operating systems as they have for the same operating systems running directly on hardware. The same is true for
applications running on guest OSs: if the organization has a security policy for an application, it should apply the same regardless of whether the application is running on an OS within a hypervisor or on an OS running on hardware.
~~~~

## R087
Document: DODI 8410.03  |  chunk 34  |  page 18

Quote (the requirement text to judge):
> SLAs and other agreements that include tactical edge and non-tactical edge networks shall take into consideration the unique characteristics of tactical edge networks; however these characteristics shall not be used to exempt tactical edge and non-tactical edge networks from the requirement to have SLAs.

Chunk 34 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[4.  SLAs]

- c.  SLAs and other agreements that include tactical edge and non-tactical edge networks shall take into consideration the unique characteristics of tactical edge networks (e.g., dynamic, adhoc, bandwidth constrained, and intermittent connections); however these characteristics shall not be used to exempt tactical edge and non-tactical edge networks from the requirement to have SLAs.  Implementation of SLAs for tactical edge and non-tactical edge networks shall not impact network or mission effectiveness.
- d.  NM SLAs and other agreements shall be structured to complement or extend other SLAs entered into by DoD Components.  If desired, an NM SLA or equivalent could be made part of the overall SLA, or similar agreement addressing the networks being managed.
- e.  NM SLAs and other agreements shall establish baseline and minimum service levels and address provisioning and measurement of the following network performance parameters:
- (1)  Network latency and packet loss on per-hop and end-to-end basis by traffic type.
- (2)  Minimum and maximum bandwidth provided.
- (3)  Mean time between failures of network equipment or connectivity.
~~~~

Previous chunk 33:
~~~~text
[4.  SLAs]

- (b)  Required NM data update rates.
- (c)  Maximum allowable time from when an event takes place to when it is reported by the NM system, as well as the location of event.
- (d)  Location of the NM event.
- (e)  Allowable NM system initialization time and data sync (or data re-sync due to NM and radio reconnection).
- (f)  Required local event storage requirements (if any).
- (g)  Reporting formats, destinations, and update rates (if finished reports are to be provided.
- (h)  Mechanisms for enforcement, auditing, and assurance.
- (6)  A description of NM system backup, recovery and continuity of operations requirement.
- (7)  Procedures for changing and terminating the SLA.
- (8)  A description of the remedies available to the customer in the event the NM system does not perform as agreed.
~~~~

## R088
Document: DODI 8410.03  |  chunk 38  |  page 20

Quote (the requirement text to judge):
> These standards shall be maintained by DISA and incorporated into the baseline schemas for NM.

Chunk 38 (the quote is marked ⟦ ⟧ where it appears):
(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)
~~~~text
[5.  NM SECURITY]

6.  NM STANDARDS AND SCHEMAS FOR TACTICAL EDGE NE.  To support end-to-end SA and NM system reporting criteria, common NM standards are required to support spectrumdependent systems and tactical edge NEs.
- a.  In consideration of tactical edge NM requirements, the DoD Components with DISA support shall jointly establish NM standards for tactical edge NEs.  The standards shall be maintained by DISA and incorporated into the baseline schemas for NM.  These standards shall consider the unique properties of tactical networking, including but not limited to:
- (1)  The ad-hoc nature of such networks.
- (2)  The requirement for NEs to connect and disconnect at random due to mobility-related constraints.
- (3)  The often limited bandwidth available.
- (4)  Operational requirements to remain in a non-transmitting state for extended periods of time.
- b.  As requested, DISA shall support program managers, in the incorporation of these standards into new or existing programs of record.
~~~~

Previous chunk 37:
~~~~text
[5.  NM SECURITY]

- c.  NM system operator and supervisory positions (e.g., system administrators, network managers and controllers, router and switch administrators, managers and controllers) performing NM IA functions as defined in DoD 8570.01-M (Reference (ad)) shall be designated IA Technical Category Level 2 and IA Management Category Level 2 positions and as critical sensitive positions as defined by DoD 5200.2-R (Reference (ae)), and military, government civilian, and contractor personnel filling them shall meet all required background checks, training, and certification requirements prior to assuming their duties.
- d.  Access to NM systems shall be authorized by the appropriate unit level commander responsible for the NM system.  Only those users with proper credentials and access authorizations will be granted access to NM systems.  NM system users shall comply with the applicable cybersecurity training and certification requirements IAW Reference (ad).
- e.  NM functions are critical within the network infrastructure.  Accordingly, supply chain risk management shall be applied to the acquisition of NM functionality IAW DoDI 5200.44 (Reference (af)) and DoDI 5200.39 (Reference (ag)).
~~~~

## R089
Document: NIST.SP.800-125  |  chunk 12  |  page 7

Quote (the requirement text to judge):
> Planning helps ensure that the virtual environment is as secure as possible and in compliance with all relevant organizational policies.

Chunk 12 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[Carefully plan the security for a full virtualization solution before installing, configuring, and deploying it.]

⟦Planning helps ensure that the virtual environment is as secure as possible and in compliance with all relevant organizational policies.⟧ Security should be considered from the initial planning stage at the beginning of the systems development life cycle to maximize security and minimize costs. It is much more difficult and expensive to address security after deployment and implementation.
~~~~

Previous chunk 11:
~~~~text
[Ensure that the hypervisor is properly secured.]

Securing a hypervisor involves actions that are standard for any type of software, such as installing updates as they become available. Other recommended actions that are specific to hypervisors include disabling unused virtual hardware; disabling unneeded hypervisor services such as clipboard- or filesharing; and considering using the hypervisor's capabilities to monitor the security of each guest OS running within it, as well as the security of activity occurring between guest OSs. The hypervisor itself also needs to be carefully monitored for signs of compromise. It is also important to provide physical access controls for the hardware on which the hypervisor runs. For example, hosted hypervisors are typically controlled by management software that can be used by anyone with access to the keyboard and mouse. Even bare metal hypervisors require physical security: someone who can reboot the host computer that the hypervisor is running on might be able to alter some of the security settings for the hypervisor.
~~~~

## R090
Document: DODI 8410.03  |  chunk 28  |  page 16

Quote (the requirement text to judge):
> Standard formats and identifications shall be maintained in a DoD-published MIB data format and dictionary established and maintained by DISA.

Chunk 28 (the quote is marked ⟦ ⟧ where it appears):
~~~~text
[3.  NM USE OF SNMP]

- a.  All SNMP MIBs used in the DoD shall comply with technical standards in the DISR and DISA Security Technical Implementation Guides (STIGs).
- b.  All MIBs along with full descriptions of their use and format shall be stored in an MIB registry managed and published by DISA.
- c.  Where possible, elements in multiple MIBs that refer to the same parameter shall be formatted and identified the same way.  ⟦Standard formats and identifications shall be maintained in a DoD-published MIB data format and dictionary established and maintained by DISA.⟧
- d.  New SNMP managed resources and management applications shall use the latest approved version of SNMP, to take advantage of the additional security features provided with this version of the protocol.  Existing systems that use SNMP shall transition to the latest approved SNMP version when feasible.
- e.  The latest version of SNMP shall be implemented with a security model appropriate to the security of the network rather than the default model.
- f.  Existing systems that use SNMP v1 or v2c shall implement the following security precautions in the period prior to transition to the latest approved version of SNMP:
~~~~

Previous chunk 27:
~~~~text
[2.  NM DATA EXCHANGE GUIDELINES]

- i.  The CDRUSSTRATCOM, in coordination with DISA and the DoD Components, shall define a minimum set of standards and values for reporting  information based on International Telegraph and Telephone Consultative Committee (CCITT) Recommendation X.731 (Reference (y)) and other applicable IETF, Distributed Management Task Force, and TM Forum standards.
~~~~
