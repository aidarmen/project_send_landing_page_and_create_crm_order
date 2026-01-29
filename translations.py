"""
Translation system for landing page.
Supports Russian (ru) and Kazakh (kk) languages.
"""

TRANSLATIONS = {
    "ru": {
        # Navigation
        "online_connection": "Онлайн-подключение",
        
        # Service types
        "internet": "Интернет",
        "mobile": "Мобильная связь",
        "tv": "Телевидение",
        "home_phone": "Домашний телефон",
        "sim_devices": "SIM для устройств",
        
        # Hero section
        "price": "Цена",
        "price_per_month": "Цена за месяц",
        "per_month": "/мес",
        "hero_description": "Ниже - состав пакета. Нажмите «Согласен», чтобы подтвердить подключение на условиях тарифа.",
        # Hero
        "hero_title": "ПОДКЛЮЧАЙТЕСЬ СО СВОИМ НОМЕРОМ",
        "promo_label": "АКЦИЯ",
        "card_40gb": "40 ГБ",
        "card_250min": "250 МИН",
        "card_tv": "TV+",
        "card_sim": "1 SIM",
        "price_promo_caption": "ЗА 3 МЕСЯЦА АКЦИИ",
        "deadline": "ДО 1 ФЕВРАЛЯ",
        "banner_note": "Акция действует 3 месяца после подключения, далее - 2589₸/мес.",
        "card_sms": "100 SMS",
        "family_offer": "Переход всей семьёй - 3 SIM × 1295 = 3885 ₸",
        
        # Content section
        "what_included": "Что входит",
        "package_individual": "Пакет сформирован индивидуально",
        "package_not_specified": "Состав пакета не указан.",
        "service_params_in_contract": "Параметры услуги указаны в договоре ниже.",
        
        # Component labels
        "speed_up_to": "До",
        "mbps": "Мбит/с",
        "home_internet": "Домашний интернет",
        "sim": "SIM",
        "data": "Интернет",
        "gb": "ГБ",
        "after_limit": "После лимита",
        "kbps": "Кбит/с",
        "within_network": "Внутри сети",
        "other_city": "Другие/городские",
        "minutes": "мин",
        "unlimited": "Безлимит",
        "channels": "каналов",
        "online_cinemas": "Онлайн-кинотеатры",
        "tv_plus_included": "Подписка TV+ включена для каждой SIM",
        
        # Sidebar
        "to_be_determined": "Уточняется",
        "your_data": "Ваши данные",
        "account_number": "Лицевой счет",
        "address": "Адрес",
        "zip_code": "Индекс",
        
        # Benefits list
        "home_internet_up_to": "Домашний интернет до",
        "mobile_internet": "Мобильный интернет",
        "tv_channels": "ТВ-каналов",
        "home_phone_in_package": "Домашний телефон в пакете",
        "sim_for_devices": "SIM для устройств",
        
        # Forms
        "read_and_agree": "Я прочитал(а) условия ниже и согласен(а)",
        "agree": "Согласен",
        "reject": "Отказаться",
        "consent_notice": "Нажимая «Согласен», вы даёте согласие на подключение указанных услуг и обработку данных. Фиксируются время, IP и User-Agent. Ссылка одноразовая и может истечь.",
        
        # Terms section
        "terms_title": "Условия предоставления услуг",
        "terms_1": "Услуги предоставляются на ежемесячной основе; оплата - помесячно.",
        "terms_2": "Скорость «до» заявленной и может меняться в зависимости от нагрузки сети и технической возможности.",
        "terms_3": "Оборудование предоставляется на период договора и подлежит возврату при расторжении.",
        "terms_4": "Мы можем изменять условия с уведомлением не менее чем за 30 дней.",
        "terms_5": "Применяется политика допустимого использования и правила оператора связи.",
        "privacy_title": "Конфиденциальность",
        "privacy_text": "Мы обрабатываем только необходимые данные, не отслеживаем контент трафика, за исключением случаев, предусмотренных законом для обеспечения безопасности сети.",
        "security_notice": "Ваше согласие фиксируется в журнале (время, IP, браузер). Токен одноразовый.",
        "operator_notice": "Все услуги предоставляются в соответствии с правилами оператора связи.",
        # Decision pages
        "accepted_heading": "Спасибо! Согласие получено",
        "accepted_confirmed": "Вы подтвердили подключение:",
        "package_contents": "Состав пакета:",
        "time_recorded": "Время фиксации (UTC):",
        "to_home": "На главную",
        "close_window": "Закрыть окно",
        "rejected_heading": "Отказ зафиксирован",
        "rejected_text": "Вы отказались от подключения:",
        "rejected_help": "Если это ошибка - обратитесь в поддержку или запросите новую ссылку.",
        "decision_error_title_default": "Ошибка",
        "decision_error_message_default": "Произошла ошибка при обработке ссылки.",
        
        # Footer
        "all_rights_reserved": "Все права защищены",
        "license": "Лицензия Nº14014826 от 09.10.2014 выдана Комитетом связи, информатизации Министерства по Инвестициям и развитию Республики Казахстан",
        
        # Address format
        "house": "д.",
        "flat": "кв.",
    },
    "kk": {
        # Navigation
        "online_connection": "Онлайн-қосылу",
        
        # Service types
        "internet": "Интернет",
        "mobile": "Ұялы байланыс",
        "tv": "Теледидар",
        "home_phone": "Үй телефоны",
        "sim_devices": "Құрылғыларға арналған SIM",
        
        # Hero section
        "price": "Баға",
        "price_per_month": "Айына баға",
        "per_month": "/ай",
        "hero_description": "Төменде - пакет құрамы. Тариф шарттары бойынша қосылуды растау үшін «Келісемін» батырмасын басыңыз.",
        # Hero
        "hero_title": "ӨЗ НӨМІРІҢІЗБЕН ҚОСЫЛЫҢЫЗ",
        "promo_label": "АКЦИЯ",
        "card_40gb": "40 ГБ",
        "card_250min": "250 МИН",
        "card_tv": "TV+",
        "card_sim": "1 SIM",
        "price_promo_caption": "АКЦИЯНЫҢ 3 АЙЫҒА",
        "deadline": "1 АҚПАНҒА ДЕЙІН",
        "banner_note": "Акция қосылғаннан кейін 3 ай бойы жарамды, одан әрі - 2589₸/ай.",
        "card_sms": "100 SMS",
        "family_offer": "Отбасыға ауысу - 3 SIM × 1295 = 3885 ₸",
        
        # Content section
        "what_included": "Не кіреді",
        "package_individual": "Пакет жеке қалыптастырылған",
        "package_not_specified": "Пакет құрамы көрсетілмеген.",
        "service_params_in_contract": "Қызмет параметрлері төмендегі келісімде көрсетілген.",
        
        # Component labels
        "speed_up_to": "Дейін",
        "mbps": "Мбит/с",
        "home_internet": "Үй интернеті",
        "sim": "SIM",
        "data": "Интернет",
        "gb": "ГБ",
        "after_limit": "Лимиттен кейін",
        "kbps": "Кбит/с",
        "within_network": "Желі ішінде",
        "other_city": "Басқа/қалалық",
        "minutes": "мин",
        "unlimited": "Шексіз",
        "channels": "арна",
        "online_cinemas": "Онлайн-кинотеатрлар",
        "tv_plus_included": "TV+ жазылым әрбір SIM-ге қосылған",
        
        # Sidebar
        "to_be_determined": "Анықталады",
        "your_data": "Сіздің деректеріңіз",
        "account_number": "Жеке шот",
        "address": "Мекен-жай",
        "zip_code": "Индекс",
        
        # Benefits list
        "home_internet_up_to": "Үй интернеті дейін",
        "mobile_internet": "Ұялы интернет",
        "tv_channels": "ТВ-арна",
        "home_phone_in_package": "Пакеттегі үй телефоны",
        "sim_for_devices": "Құрылғыларға арналған SIM",
        
        # Forms
        "read_and_agree": "Мен төмендегі шарттарды оқыдым және келісемін",
        "agree": "Келісемін",
        "reject": "Бас тарту",
        "consent_notice": "«Келісемін» батырмасын басу арқылы сіз көрсетілген қызметтерді қосуға және деректерді өңдеуге келісім бересіз. Уақыт, IP және User-Agent тіркеледі. Сілтеме бір реттік және мерзімі өтуі мүмкін.",
        
        # Terms section
        "terms_title": "Қызметтерді көрсету шарттары",
        "terms_1": "Қызметтер ай сайын көрсетіледі; төлем - ай сайын.",
        "terms_2": "«Дейін» көрсетілген жылдамдық желі жүктемесіне және техникалық мүмкіндіктерге байланысты өзгеруі мүмкін.",
        "terms_3": "Жабдық келісім мерзіміне беріледі және келісімді бұзу кезінде қайтарылуға жатады.",
        "terms_4": "Біз кемінде 30 күн бұрын хабарлаумен шарттарды өзгерте аламыз.",
        "terms_5": "Рұқсат етілген пайдалану саясаты және байланыс операторының ережелері қолданылады.",
        "privacy_title": "Құпиялылық",
        "privacy_text": "Біз тек қажетті деректерді өңдейміз, желінің қауіпсіздігін қамтамасыз ету үшін заңмен қарастырылған жағдайлардан басқа трафик мазмұнын қадағаламаймыз.",
        "security_notice": "Сіздің келісіміңіз журналда тіркеледі (уақыт, IP, браузер). Токен бір реттік.",
        "operator_notice": "Барлық қызметтер оператор ережелері бойынша көрсетіледі.",
        # Decision pages (kk)
        "accepted_heading": "Рахмет! Келісім тіркелді",
        "accepted_confirmed": "Сіз қосылуды растадыңыз:",
        "package_contents": "Пакет құрамы:",
        "time_recorded": "Тіркелген уақыт (UTC):",
        "to_home": "Басты бет",
        "close_window": "Терезені жабыңыз",
        "rejected_heading": "Қабылданбады",
        "rejected_text": "Сіз қосылудан бас тарттыңыз:",
        "rejected_help": "Егер қате болса - қолдау қызметіне хабарласыңыз немесе жаңа сілтеме сұраңыз.",
        "decision_error_title_default": "Қате",
        "decision_error_message_default": "Сілтемені өңдеу кезінде қате пайда болды.",
        
        # Footer
        "all_rights_reserved": "Барлық құқықтар қорғалған",
        "license": "№14014826 лицензиясы 2014 жылдың 09.10 күні Қазақстан Республикасы Инвестициялар және даму министрлігінің Байланыс, ақпараттандыру комитеті берген",
        
        # Address format
        "house": "үй",
        "flat": "пәтер",
    }
}


def get_translation(lang: str, key: str, default: str = None) -> str:
    """
    Get translation for a given language and key.
    
    Args:
        lang: Language code ('ru' or 'kk')
        key: Translation key
        default: Default value if translation not found
    
    Returns:
        Translated string or default value
    """
    if lang not in TRANSLATIONS:
        lang = "ru"  # Fallback to Russian
    
    return TRANSLATIONS.get(lang, {}).get(key, default or key)


def get_all_translations(lang: str) -> dict:
    """
    Get all translations for a given language.
    
    Args:
        lang: Language code ('ru' or 'kk')
    
    Returns:
        Dictionary of all translations for the language
    """
    if lang not in TRANSLATIONS:
        lang = "ru"  # Fallback to Russian
    
    return TRANSLATIONS.get(lang, {})

