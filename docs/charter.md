# Charter

## Purpose

Timmeny-ToDo-OS is a personal operating system for todo and action-item capture: a practical layer for routing tasks into the right Monday.com boards.

The first job of this repository is to make the system explicit. Before adding complexity, it should capture the operating principles, name the workflows that matter, and define simple interfaces between people, tools, and agents.

## Scope

Early scope includes:

- Personal knowledge and decision records
- Repeatable project workflows
- Automation recipes with clear ownership
- Agent prompts and task handoff patterns
- Local scripts or services that support those workflows

Out of scope for the initial foundation:

- A full desktop operating system
- Heavy platform architecture before concrete workflows exist
- Hidden automations that cannot explain what they changed

## Design Bias

Start with boring, inspectable files. Prefer Markdown, small scripts, and explicit conventions until a real bottleneck justifies a stronger abstraction.

Every automation should answer three questions:

1. What did it read?
2. What did it decide?
3. What did it change?

## First Milestones

1. Capture the core workflows.
2. Define the repository layout.
3. Add one complete workflow from trigger to output.
4. Document how to run, review, and revise that workflow.
