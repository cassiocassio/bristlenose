# Speaker Identification

<!-- Variables: {transcript_sample}, {speaker_list} -->

## System

You are an expert at analysing user-research interview transcripts.

## User

Below is the first ~5 minutes of a user-research interview transcript.
The speakers have been labelled automatically (e.g. "Speaker A", "Speaker B", or by name).

Your task: identify the role of each speaker.

Roles:
- **researcher**: The person conducting the research session. They ask structured questions, give instructions, facilitate discussion, and guide the participant through tasks or screens.
- **participant**: The research subject. They respond to questions, share opinions, attempt tasks, and provide feedback.
- **observer**: A silent or near-silent attendee (e.g. note-taker, stakeholder). They speak very little or not at all.

Transcript sample:
{transcript_sample}

Speakers found: {speaker_list}

For each speaker, assign exactly one role and explain your reasoning briefly.

Additionally, for each speaker:
- **person_name**: If the speaker introduces themselves or is addressed by name in the transcript, provide their real name. Leave empty if no name is mentioned.
- **job_title**: If the speaker mentions their job title, role, or professional activity (e.g. "I'm a product manager", "I work in design"), provide it. Leave empty if not mentioned.
