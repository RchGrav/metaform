# Connect budget evidence (2026-10-14)

Guard test failure with the budget line removed from connect_instructions:

    >       assert len(sent) <= 2048 and 'write-workflow' in sent and 'FIRST RUN' in sent
    E       AssertionError: assert (2785 <= 2048)

Measurement, registered folder with no intake, METAFORM_ROLE unset:

    default startup 1781 total 1975 index '\nSkills: load one with metaform_skills op=list name=logic.skill.<name>.\ncode-links, import-workflow, prompt-efficiency, scan,'
    every startup 1911 total 1911 index ''

The full description index alone is 993 characters. Startup with the FIRST RUN notice is 1911 to 2033 characters, so even the names-only form cannot fit once every shipped module is on.
