{
    'name': 'Dynamic Sales Request',
    'version': '20.0.1.0.0',
    'category': 'Sales',
    'summary': 'Survey Sales Request Management with autocomplete and product lines',
    'author': 'Bizoft Enterprise',
    'license': 'LGPL-3',
    'depends': ['survey', 'sale'],
    'data': [
        'views/survey_question_views.xml',
        'views/survey_templates.xml',
    ],
    'assets': {
        'survey.survey_assets': [
            'custom_survey/static/src/js/staff_selection.js',
            'custom_survey/static/src/js/product_lines.js',
            'custom_survey/static/src/scss/staff_selection.scss',
        ],
    },
    'installable': True,
    'application': False,
}