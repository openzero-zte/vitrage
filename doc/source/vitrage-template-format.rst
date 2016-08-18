================================
Vitrage Templates Format & Usage
================================

Overview
========
In Vitrage we use configuration files, called "templates", to express rules
regarding raising deduced alarms, setting deduced states, and detecting/setting
RCA links.
This page describes the format of the Vitrage templates, with some examples and
open questions on extending this format. Additionally, a short guide on adding
templates is presented.

Template Structure
==================
The template is written in YAML language, with the following structure.
 ::

  metadata:
    name: <unique template identifier>
    description: <what this template does>
  definitions:
    entities:
        - entity: ...
        - entity: ...
    relationships:
        - relationship: ...
        - relationship: ...
  scenarios:
      - scenario:
          condition: <if statement true do the action>
          actions:
              - action: ...


The template is divided into three main sections:

- *metadata:* Contains the template name, and brief description of what the template does (optional)
- *definitions:* This section contains the atomic definitions referenced later on, for entities and relationships
   - *entities –* describes the resources and alarms which are relevant to the template scenario (conceptually, corresponds to a vertex in the entity graph)
   - *relationships –* the relationships between the entities (conceptually, corresponds to an edge in the entity graph)
- *scenarios:* A list of if-then scenarios to consider. Each scenario is comprised of:
   - *condition –* the condition to be met. This condition will be phrased referencing the entities and relationships previously defined.
   - *action(s) –* a list of actions to execute when the condition is met.

Condition Format
----------------
The condition which needs to be met will be phrased using the entities and
relationships previously defined. An expression is either a *single* entity,
or some logical combination of relationships.
Expression can be combined using the following logical operators:

- "and" - indicates both expressions must be satisfied in order for the
  condition to be met.
- "or" - indicates at least one expression must be satisfied in order for the
  condition to be met (non-exclusive or).
- parentheses "()"  - clause indicating the scope of an expression.

The following are examples of valid expressions, where X, Y and Z are
relationships:

- X
- X and Y
- X and Y and Z
- X and not Y
- X and not (Y or Z)
- X and not X

Examples
========

Example 1: Basic RCA and Deduced Alarm/State
--------------------------------------------
The following template demonstrates

1. How to raise a deduced alarm. Specifically, if there is high CPU load on a
   host, raise alarm indicating CPU performance problems on all contained
   instances.
2. How to link alarms for purposes of root cause analysis (RCA). Specifically,
   if there is high CPU load on the host and CPU performance problems on the
   hosted instances, we link them with a "causes" relationship.
3. How to use a single template for several different scenarios.

 ::

    metadata:
        name: host_high_mem_load_to_instance_mem_suboptimal
        description: when there is high memory on the host, show implications on the instances
    definitions:
        entities:
            - entity:
                category: ALARM
                type: host_high_mem_load
                template_id: host_alarm # some string
            - entity:
                category: ALARM
                type: instance_mem_performance_problem
                template_id: instance_alarm
            - entity:
                category: RESOURCE
                type: nova.host
                template_id: host
            - entity:
                category: RESOURCE
                type: nova.instance
                template_id: instance
        relationships:
            - relationship:
                source: host_alarm  # source and target from entities section
                target: host
                relationship_type: on
                template_id : alarm_on_host
            - relationship:
                source: instance_alarm
                target: instance
                relationship_type: on
                template_id : alarm_on_instance
            - relationship:
                source: host
                target: instance
                relationship_type: contains
                template_id : host_contains_instance
    scenarios:
        - scenario:
            condition: alarm_on_host and host_contains_instance # condition uses relationship ids
            actions:
                - action:
                   action_type: raise_alarm
                   properties:
                      alarm_name: instance_mem_performance_problem
                      severity: warning
                   action_target:
                      target: instance # entity template_id
                - action:
                   action_type: set_state
                   properties:
                      state: suboptimal
                   action_target:
                      target: instance # entity template_id
        - scenario:
            condition: alarm_on_host and alarm_on_instance and host_contains_instance
            actions:
                - action:
                   action_type: add_causal_relationship
                   action_target:
                      source: host_alarm
                      target: instance_alarm

Example 2: Deduced state based on alarm
---------------------------------------
The following template will change the state of a resource to "ERROR" if there
is any alarm of severity "CRITICAL" on it.

 ::

    metadata:
        id: deduced_state_for_all_with_alarm
        description: deduced state for all resources with alarms
    definitions:
        entities:
            - entity:
                category: RESOURCE
                template_id: a_resource # entity ids are any string
            - entity:
                category: ALARM
                severity: critical
                template_id: high_alarm # entity ids are any string
        relationships:
            - relationship:
                source: high_alarm
                target: a_resource
                relationship_type: on
                template_id : high_alarm_on_resource
    scenarios:
        - scenario:
            condition: high_alarm_on_resource
            actions:
                - action:
                   action_type : set_state
                   properties:
                      state: error
                   action_target:
                      target: a_resource

Example 3: Deduced alarm based on state
---------------------------------------
This template will cause an alarm to be raised on any Host in state "ERROR"

Note that in this template, there are no relationships. The condition is just
that the entity exists. Also note that the states and severity are
case-insensitive.

 ::

    metadata:
        name: deduced_alarm_for_all_host_in_error
        description: raise deduced alarm for all hosts in error
    definitions:
        entities:
            - entity:
                category: RESOURCE
                type: nova.host
                state: error
                template_id: host_in_error
    scenarios:
        - scenario:
            condition: host_in_error
            actions:
                - action:
                   action_type: raise_alarm
                   properties:
                      alarm_name: host_in_error_state
                      severity: critical
                   action_target:
                      target: host_in_error

Example 4: Deduced Alarm triggered by several options
-----------------------------------------------------
This template will raise a deduced alarm on an instance, which can be caused by
an alarm on the hosting zone or an alarm on the hosting host.

 ::

    metadata:
        name: deduced_alarm_two_possible_triggers
        description: deduced alarm using or in condition
    definitions:
        entities:
            - entity:
                category: ALARM
                type: zone_connectivity_problem
                template_id: zone_alarm
            - entity:
                category: ALARM
                type: host_connectivity_problem
                template_id: host_alarm
            - entity:
                category: RESOURCE
                type: nova.zone
                template_id: zone
            - entity:
                category: RESOURCE
                type: nova.host
                template_id: host
            - entity:
                category: RESOURCE
                type: nova.instance
                template_id: instance
        relationships:
            - relationship:
                source: zone_alarm
                target: zone
                relationship_type: on
                template_id : alarm_on_zone
            - relationship:
                source: zone_alarm
                target: zone
                relationship_type: on
                template_id : alarm_on_host
            - relationship:
                source: zone
                target: host
                relationship_type: contains
                template_id : zone_contains_host
            - relationship:
                source: host
                target: instance
                relationship_type: contains
                template_id : host_contains_instance
    scenarios:
        - scenario:
            condition: (alarm_on_host and host_contains_instance) or (alarm_on_zone and zone_contains_host and host_contains_instance)
            actions:
                - action:
                   action_type : raise_alarm
                   properties:
                      alarm_name: instance_connectivity_problem
                      severity: critical
                   action_target:
                      target: instance


Usage
=====

Adding/removing a template
--------------------------

- Ensure all the templates you wish to use are placed here: *<vitrage folder>/templates*.
- Restart *vitrage-graph*.
- The template will be validated before loading. Validation errors are written
  to the log. Templates with validation errors are skipped.

Common parameters and their acceptable values - for writing templates
---------------------------------------------------------------------

+-------------------+---------------+-------------------------+------------------------------------+
| block             | key           | supported values        | comments                           |
+===================+===============+=========================+====================================+
| entity            | category      | ALARM                   |                                    |
|                   |               | RESOURCE                |                                    |
+-------------------+---------------+-------------------------+------------------------------------+
| entity (ALARM)    | type          | any string              |                                    |
+-------------------+---------------+-------------------------+------------------------------------+
| entity (RESOURCE) | type          | openstack.cluster,      | These are for the datasources that |
|                   |               | nova.zone,              | come with vitrage by default.      |
|                   |               | nova.host,              | Adding datasources will add more   |
|                   |               | nova.instance,          | supported types, as defined in the |
|                   |               | cinder.volume,          | datasource transformer             |
|                   |               | switch                  |                                    |
+-------------------+---------------+-------------------------+------------------------------------+
| action            | action_type   | raise_alarm,            |                                    |
|                   |               | set_state,              |                                    |
|                   |               | add_causal_relationship |                                    |
|                   |               | mark_down               |                                    |
+-------------------+---------------+-------------------------+------------------------------------+


Supported Actions
-----------------

raise_alarm
^^^^^^^^^^^
Raise a deduced alarm on a target entity
 ::

    action:
        action_type : raise_alarm
            properties:
                alarm_name: some problem # mandatory; string that is valid variable name
                severity: critical       # mandatory; should match values in "vitrage.yaml"
            action_target:
                target: instance         # mandatory. entity (from the definitions section) to raise an alarm on. Should not be an alarm.

set_state
^^^^^^^^^^^
Set state of specified entity. This will directly affect the state as seen in vitrage, but will not impact the state at the relevant datasource of this entity.
 ::

    action:
        action_type : set_state
            properties:
                state: error # mandatory; should match values in the relevant datasource_values YAML file for this entity.
            action_target:
                target: host # mandatory. entity (from the definitions section) to change state


add_causal_relationship
^^^^^^^^^^^
Add a causal relationship between alarms.
 ::

    action:
        action_type : add_causal_relationship
            action_target:
                source: host_alarm     # mandatory. the alarm that caused the target alarm (name from the definitions section)
                target: instance_alarm # mandatory. the alarm that was caused by the source alarm (name from the definitions section)


mark_down
^^^^^^^^^
Set an entity marked_down field.
This can be used along with nova notifier to call force_down for a host
 ::

    action:
        action_type : mark_down
            action_target:
                target: host # mandatory. entity (from the definitions section, only host) to be marked as down

Future support & Open Issues
============================

Negation
--------
We need to support a "not" operator, that indicates the following expression
must not be satisfied in order for the condition to be met. "not" should apply
to relationships, not entities. Then we could have a condition like

 ::

    condition: host_contains_instance and not alarm_on_instance


Inequality
----------
Consider a template that has two entities of the same category+type, say E1 and
E2 both are instances like this:

 ::

    metadata:
        name: two_similar_instances
    definitions:
        entities:
            - entity:
                category: RESOURCE
                type: nova.host
                template_id: host
            - entity:
                category: RESOURCE
                type: nova.instance
                template_id: instance1
            - entity:
                category: RESOURCE
                type: nova.instance
                template_id: instance2
            ...
        relationships:
            - relationship:
                source: host
                target: instance1
                relationship_type: contains
                template_id: link1
            - relationship:
                source: host
                target: instance2
                relationship_type: contains
                template_id: link2

            ...

There are three options of how to interpret this template:

- *instance1 == instance2.* This option is not a reasonable one, as in this
  case the template can be written with only *instance1*
- *instance1 != instance2.*
- *instance1 != instance2 or instance1 == instance2.* In other words, either
  option is fine.

Thus, we need a way to distinguish between options 2 & 3 (as option 1 can be
expressed by using only instance1). This can be done in two ways:
1. Introducing another logical operator "neq", to be used between expressions:

 ::

    condition: (instance1 neq instance2) and...

2. Using this as a relationship type "neq":

 ::

    relationship:
        source: instance1
        target: instance2
        relationship_type: neq


Cardinality
-----------
To support cardinality, for example to express we want a host to have two
instances on it, we could take different approaches.

1. One approach would rely on the "neq" relationship described above. Similar
to the example given in the previous section, stating that the two instances on
the host are not equal is equivalent to a cardinality of two.
2. A different approach would be to expand the definition of the "relationship"
clause. By default cardinality=1 (which will support backward compatibility)

For example, we might use the one of the following formats

::

    - relationship: # option A
        source: host
        target: instance
        target_cardinality: 2 # two instances, but only one host
        relationship_type: contains
        template_id: host_contains_two_instances_A

    - relationship: # option B, same as option A but split into two lines
        source: host
        target: instance
        cardinality_for: instance
        cardinality: 2
        relationship_type: contains
        template_id: host_contains_two_instances_B
