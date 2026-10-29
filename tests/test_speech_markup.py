import xml.etree.ElementTree as ET
from radar_ia.speech_markup import bilingual_ssml


def test_english_tagged_and_paragraphs_preserved():
    markup=bilingual_ssml('Training loop é um termo.\n\nFine-tuning é outro.', ['training loop','fine-tuning'])
    root=ET.fromstring(markup)
    assert len(root.findall('p'))==2
    assert len(root.findall('.//lang'))==2
    assert root.find('.//lang').attrib['{http://www.w3.org/XML/1998/namespace}lang']=='en-US'


def test_input_xml_is_escaped():
    markup=bilingual_ssml('Exemplo <break/> & teste.',[])
    root=ET.fromstring(markup)
    assert [node.attrib for node in root.findall('.//break')]==[{'time':'950ms'}]
    assert '<break/>' in ''.join(root.itertext())


def test_term_not_matched_inside_longer_word():
    assert '<lang' not in bilingual_ssml('mytraining loops', ['training'])


def test_chunks_keep_paragraphs_and_english_inside_one_request():
    from radar_ia.speech_markup import speech_chunks
    text='Primeiro parágrafo.\n\nTraining loop significa ciclo de treinamento.'
    assert speech_chunks(text)==[text]


def test_chunks_prefer_paragraph_boundary():
    from radar_ia.speech_markup import speech_chunks
    assert speech_chunks('Primeiro.\n\nSegundo.', limit=15)==['Primeiro.', 'Segundo.']


def test_explicit_sentence_and_paragraph_pauses_preserve_english():
    root=ET.fromstring(bilingual_ssml('Usamos prompt caching. Ele reutiliza contexto.\n\nAgora, observability.', ['prompt caching','observability']))
    assert [b.attrib['time'] for b in root.findall('.//break')]==['450ms','950ms','950ms']
    assert [t.text for t in root.findall('.//lang')]==['prompt caching','observability']


def test_decimal_and_abbreviation_do_not_split_mid_sentence():
    from radar_ia.speech_markup import sentences
    assert sentences('O Dr. Silva usa a versão 2.5. A próxima é nova.')==['O Dr. Silva usa a versão 2.5.','A próxima é nova.']
