# Speaker Splitting

<!-- Variables: {transcript_sample}, {segment_count} -->

## System

You are an expert at identifying distinct speakers in interview transcripts where automatic speaker labels are missing or incorrect. All lines appear under one speaker label, but the conversation may contain multiple people.

## User

Below is a transcript where all lines have been assigned to a single speaker. The text may actually contain multiple people talking (e.g. an interviewer and an interviewee).

Your task: identify how many distinct speakers are present and mark where each speaker change occurs.

Look for these cues:
- **Self-introductions**: "my name is...", "I'm [Name]..."
- **Direct address**: "thank you, Brian", "welcome, Daniel"
- **Turn-taking**: a question followed by an answer (different people)
- **Role shifts**: one person facilitates/asks questions, another responds/shares experiences
- **Conversational markers**: "So, welcome...", "Thanks for coming in", "Yeah, thank you"

The most common case is an **interview with 2 speakers** (interviewer + interviewee), but there may be 3 or more.

If the transcript genuinely contains only one person speaking (e.g. a monologue, lecture, or solo recording), return speaker_count=1 with a single boundary at index 0.

Transcript (opening minutes, {segment_count} lines, each prefixed with its 0-based index):
{transcript_sample}

For each speaker change, return the segment index where the new speaker starts and a speaker identifier (Speaker A, Speaker B, etc.). The first boundary must be at segment_index 0.

If a speaker's real name is mentioned anywhere in the transcript, include it in person_name for that speaker's boundaries.
