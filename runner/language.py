"""Language is an immutable task choice, not a guess from the UI or brief."""
LANGUAGES={'en':'English','fr':'French','es':'Spanish','zh-CN':'Simplified Chinese','ja':'Japanese'}

def presentation_request(task):
    value={key:task[key] for key in ('title','brief','pages','style')}
    mode=task.get('mode','create')
    if mode not in ('create','edit'):
        raise ValueError('Unsupported task mode')
    value['mode']=mode
    if mode=='edit':
        value['pages']=None
    language=task.get('language')
    if language is not None and (not isinstance(language,str) or language not in LANGUAGES):
        raise ValueError('Unsupported presentation language')
    value['language']=language
    return value

def language_instruction(task):
    language=presentation_request(task)['language']
    if language is None:
        return 'This legacy task has no saved language choice. Follow an explicit requested output language, otherwise use the main language of its topic/brief; do not impose English retroactively.'
    return (f'The user selected {LANGUAGES[language]} ({language}) as the presentation language. '
            'Write all audience-facing slide titles, body text, chart labels, captions, conclusions and speaker notes in that language, '
            'even when the topic or brief is written in another language. This saved selection governs output language. '
            'Translate the subject faithfully; preserve proper names, product names, code and original source titles where needed. '
            'Do not add unrequested bilingual or decorative English labels. Record the language in the content outline; '
            'design for its actual text length, fonts, accents, glyphs, line breaks and number/date conventions. '
            'Inspect every rendered slide for language consistency, missing glyphs and overflow before export. '
            'Write the completion summary in the selected language too.')
