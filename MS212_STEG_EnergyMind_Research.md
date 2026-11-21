# Sagemcom MS212 Smart Meter -- STEG Tunisia Project

## 1. Identifying the meter

The photograph shows a **Sagemcom MS212** smart electricity meter
installed in a Tunisian household.

### Identification details

-   **Manufacturer:** Sagemcom
-   **Ownership marking:** STEG
-   **Manufacturing:** Tunisia
-   **Model family:** MS212
-   **Communication:** G3-PLC Hybrid
-   **Additional radio:** Wireless M-Bus, 868 MHz
-   **Application protocol:** DLMS
-   **Meter designation:** G3-Hybride

### Markings visible on the meter

  Marking         Meaning
  --------------- -----------------------------------
  MS212           Meter model
  G3-Hybride      Hybrid communication technology
  G3-PLC          Power Line Communication
  W-Mbus 868MHz   Wireless communication
  DLMS            Meter data communication protocol
  230V -- 50Hz    Electrical supply
  5(80)A          Current rating
  1000 imp/kWh    Meter pulse constant

The manufacturer's technical document is the **Sagemcom MS212 technical
datasheet**.

**Important distinction:** This is not a meter containing a collection
of independent environmental sensors. It is an electronic electricity
meter that measures electrical quantities through its internal metrology
circuitry.

That distinction matters for EnergyMind.

------------------------------------------------------------------------

## 2. Communication technologies

The meter has two communication technologies printed directly on its
casing.

### G3-PLC

-   G3-PLC means *G3 Power Line Communication*.
-   Data can travel through the existing electrical power lines.
-   It is a communication technology, not an additional electrical
    measurement sensor.

### Wireless M-Bus -- 868 MHz

-   Wireless M-Bus is a radio communication technology.
-   The meter's marking identifies operation in the 868 MHz band.
-   It can support wireless communication with compatible metering
    devices.

### DLMS/COSEM

-   DLMS/COSEM is the application-level protocol used to exchange meter
    information.
-   It defines how metering data and related information can be
    represented and communicated.

**Qualification:** The presence of both communication technologies on
the meter does not establish which one STEG currently uses for every
meter, or whether both operate simultaneously.

------------------------------------------------------------------------

## 3. What does the MS212 measure?

The manufacturer's MS212 datasheet lists capabilities beyond recording
accumulated kWh.

The following measurements and functions were identified in the
datasheet:

  Measurement / function   What it means
  ------------------------ -------------------------------------------
  Active energy            Electricity consumed, measured in kWh
  Reactive energy          Reactive energy, measured in kvarh
  Import/export energy     Energy flowing in either direction
  Voltage interruptions    Detects power loss
  Voltage restoration      Detects power returning
  Neutral current          Measures current in the neutral conductor
  Power supply quality     Monitors supply-quality events
  Power factor variation   Detects changes in power factor

The meter also has event-management and diagnostic capabilities.

This means there may be a richer dataset available than accumulated
electricity consumption alone.

**Important:** These are capabilities identified in the manufacturer's
documentation. They do not prove that every measurement is enabled in
the Tunisian STEG configuration or made available to third-party
applications.

------------------------------------------------------------------------

## 4. Can the meter detect faults or abnormal events?

The datasheet lists several fraud and abnormal-event detection
capabilities.

  Event                    What it can indicate
  ------------------------ ----------------------------------
  Strong magnetic field    Possible magnetic tampering
  Cover opening            Physical interference
  Input/output swap        Incorrect wiring or manipulation
  Phase/neutral swap       Wiring abnormality
  Mains power cut          Loss of supply
  Power factor variation   Electrical behavior change
  Neutral disturbance      Abnormal neutral conditions

The meter also mentions automatic diagnostics and tamper-event
recording/reporting.

### Why this matters

The meter can potentially provide information useful for identifying
electrical abnormalities without installing an additional sensor inside
the household.

However, **detecting an event inside the meter is not the same as STEG
exposing that event to an external AI application**. The data-access
interface and permissions still need to be established.

------------------------------------------------------------------------

## 5. Siemens' involvement in the STEG project

The research identified Siemens' involvement in the STEG Smart Grid
project.

The project responsibilities were described as follows:

  Company                     Responsibility
  --------------------------- --------------------------------
  **Siemens Advanta**         System integration
  **Siemens Grid Software**   Meter Data Management software
  **Sagemcom**                Smart-meter supply
  **eFluid**                  Customer Information System
  **Sia Partners**            Project management assistance

The French Treasury was identified as an independent source confirming
project responsibilities.

### What does Siemens provide?

The Siemens platform identified in the project is **GridscaleX Meter
Data Management**, formerly known as **EnergyIP MDM**.

Its purpose is to manage meter data at utility scale.

The platform supports:

-   Meter data management.
-   Meter-to-cash processes.
-   Consumption forecasting.
-   Data integration.
-   Operational efficiency.

Siemens reported that the 500,000-meter pilot was put into production in
May 2025, with nationwide expansion targeting approximately 5.5 million
smart meters.

### The roles in simple terms

-   **Sagemcom:** Makes and supplies the smart meter.
-   **Siemens:** Provides system integration and meter-data management
    technology.
-   **STEG:** Operates the electricity distribution service and the
    smart-meter programme.

------------------------------------------------------------------------

## 6. How data travels from the meter to Siemens

Based on the published project architecture, the following is a
**conceptual representation** of the data flow:

``` text
┌──────────────────────────────┐
│      Sagemcom MS212          │
│                              │
│ Measures electricity and    │
│ records readings / events   │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│     Communication network    │
│                              │
│ G3-PLC / RF / other supported│
│ communication technologies   │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│     STEG AMI infrastructure  │
│                              │
│ Communication management    │
│ and data collection         │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Siemens GridscaleX MDMS      │
│                              │
│ Meter data management,       │
│ validation and processing    │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│          EnergyMind          │
│                              │
│ Proposed external analytics  │
│ and AI layer                 │
└──────────────────────────────┘
```

The EnergyMind connection is **proposed, not a confirmed existing STEG
integration**.

The important question is whether EnergyMind could obtain data from the
Meter Data Management System (MDMS) through an API, data export, or
another authorized interface.

Public documentation identified in the research does not yet establish
that access.

------------------------------------------------------------------------

## 7. What this means for EnergyMind

Based on the actual MS212 capabilities, five research directions are
particularly relevant.

  -----------------------------------------------------------------------
  Priority                Feature                 Potential input
  ----------------------- ----------------------- -----------------------
  1                       Consumption anomaly     Active energy and load
                          detection               profiles

  2                       Power-quality           Voltage interruptions
                          monitoring              and restoration

  3                       Electrical abnormality  Neutral current and
                          detection               power factor

  4                       Tampering detection     Meter event logs

  5                       Outage detection        Power-down and power-up
                                                  events
  -----------------------------------------------------------------------

### Three levels of analysis

It is useful to distinguish three different capabilities:

1.  **Meter-level detection:** Identifies events recorded by an
    individual meter.
2.  **Network-level detection:** Correlates events across multiple
    meters and electrical equipment.
3.  **Predictive detection:** Uses historical measurements and events to
    estimate future problems.

The third capability is where machine learning becomes particularly
interesting.

### Potential EnergyMind features and data requirements

  -----------------------------------------------------------------------
  EnergyMind feature                  Relationship with the MS212 / STEG
                                      infrastructure
  ----------------------------------- -----------------------------------
  Consumption anomaly detection       Directly relevant to active-energy
                                      readings and load profiles

  Power-quality monitoring            Potentially relevant to voltage
                                      interruption and restoration events

  Electrical abnormality detection    Potentially relevant to neutral
                                      current and power-factor
                                      information

  Tampering detection                 Potentially relevant to meter event
                                      logs

  Outage detection                    Potentially relevant to power-down
                                      and power-up events

  Load forecasting                    Relevant to historical consumption
                                      and load curves

  Feeder-level monitoring             Requires network topology and GIS
                                      integration

  Predictive maintenance              Requires historical faults and
                                      equipment information
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 8. Local access interfaces

A detail visible in the photograph is the marking:

**PC: DSMR**

The manufacturer's datasheet also identifies a P1 DSMR interface and an
optical port. These are potential local access interfaces.

However, the exact configuration, available data, physical interface
details, and STEG access restrictions must be verified before attempting
to use them.

The existence of an interface does not automatically mean that all meter
data can be read through it, or that connecting external equipment is
permitted.

------------------------------------------------------------------------

## 9. Official and technical sources identified

The previous research identified the following sources as the most
useful documents for understanding the meter and the project.

  -----------------------------------------------------------------------
  Source                              What it is useful for
  ----------------------------------- -----------------------------------
  **Sagemcom MS212 technical          Technical specifications,
  datasheet**                         communication, metrology, fraud
                                      detection and power quality

  **Siemens -- STEG Smart Grid        Siemens' responsibilities, MDMS,
  project case study**                pilot deployment and nationwide
                                      expansion

  **French Treasury -- STEG Smart     Financing, procurement, partners
  Grid**                              and project deployment

  **STEG -- Programme Smart Grid**    Original deployment zones,
                                      objectives and AMI architecture
  -----------------------------------------------------------------------

The source references appeared in the research conversation as:

-   Sagemcom MS212 datasheet: `turn603374view0`
-   Siemens project case study: `turn603374view1`
-   French Treasury project information: `turn603374view3`
-   STEG Smart Grid project page: `turn598249search0`

These are conversation reference identifiers, not standalone URLs.
Consult the original conversation's source links to open the documents.

------------------------------------------------------------------------

## 10. Questions that still need answers

Before designing EnergyMind's data pipeline or anomaly-detection models,
the following questions should be answered.

### Meter and manufacturer

1.  Is the MS212 the standard meter model being installed in Tunisian
    households, or is it one of several models?
2.  Which measurements are enabled in the STEG configuration?
3.  What is the exact list of DLMS/COSEM objects exposed by the
    installed meter?
4.  What is the sampling or recording interval for each measurement?
5.  Which meter events are recorded, and how long are they retained?

### Communication and data collection

6.  Does STEG use G3-PLC, Wireless M-Bus, or both for this meter
    deployment?
7.  How does the meter communicate with the data collection
    infrastructure?
8.  How frequently are readings transmitted?
9.  Are event notifications transmitted immediately or collected
    periodically?
10. Can readings be retrieved locally through the P1 DSMR or optical
    interface?

### Siemens and the AMI platform

11. Which data is available through Siemens GridscaleX MDMS?
12. Does the platform expose an API or authorized data-export mechanism?
13. Can STEG provide historical meter readings and event logs?
14. Can third-party applications such as EnergyMind access anonymized or
    authorized datasets?

### Network-level analysis

15. Can meter identifiers be associated with transformers and feeders?
16. Can the AMI data be connected to STEG's GIS?
17. Are outage events correlated across multiple meters?
18. Is historical equipment-failure information available for predictive
    maintenance?

------------------------------------------------------------------------

## 11. Recommended next step

The most important next step is to establish exactly what data can be
extracted from the MS212 and what data is accessible through STEG's AMI
platform.

There are two complementary investigation paths:

### Path A --- Investigate the physical meter

Obtain the complete MS212 technical documentation and identify:

-   Available DLMS/COSEM registers and objects.
-   Measurement registers.
-   Event and alarm registers.
-   P1 DSMR interface capabilities.
-   Optical-port capabilities.
-   Communication configuration.

### Path B --- Investigate STEG's central infrastructure

Establish:

-   How meter data reaches the AMI platform.
-   What Siemens GridscaleX MDMS stores and processes.
-   Whether authorized data exports or APIs exist.
-   Whether historical data and event logs can be made available for
    research.

**The central objective:** Determine which measurements and events
EnergyMind can actually obtain, at what frequency, and at what level of
detail.

This must be established before selecting machine-learning features or
building anomaly-detection models.

------------------------------------------------------------------------

## Main takeaway

The Sagemcom MS212 is more than a digital kWh counter. Its documented
capabilities include electrical energy measurements, power-related
information, communication technologies, diagnostics and abnormal-event
detection.

The STEG Smart Grid project connects this meter ecosystem to a larger
Advanced Metering Infrastructure, with Siemens involved in system
integration and meter-data management.

For EnergyMind, the opportunity is to build an authorized analytics
layer on top of this infrastructure, using real meter readings and
events to detect consumption anomalies, power-quality issues, outages
and potentially predict future problems.

**The biggest unresolved issue is data accessibility:** the meter's
technical capabilities do not automatically tell us which data STEG
collects, stores, exposes or permits external applications to use.
