from deep_translator import GoogleTranslator

text = "היי בדיקת תרגום"
translated_en = GoogleTranslator(source='iw', target='en').translate(text)
translated_ru = GoogleTranslator(source='iw', target='ru').translate(text)

print("EN:", translated_en)
print("RU:", translated_ru)
