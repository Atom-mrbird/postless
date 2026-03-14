import iyzipay
from django.conf import settings

def get_iyzipay_options():
    options = {
        'api_key': settings.IYZICO_API_KEY,
        'secret_key': settings.IYZICO_SECRET_KEY,
        'base_url': settings.IYZICO_BASE_URL
    }
    return options

def create_checkout_form(user, request):
    options = get_iyzipay_options()
    
    # Buyer details (Sample data, should be replaced with real user data if available)
    buyer = {
        'id': str(user.id),
        'name': user.first_name or user.username,
        'surname': user.last_name or 'User',
        'gsmNumber': '+905350000000',
        'email': user.email or 'email@email.com',
        'identityNumber': '74455555555',
        'lastLoginDate': '2015-10-05 12:43:35',
        'registrationDate': '2013-04-21 15:12:09',
        'registrationAddress': 'Nisantasi',
        'ip': request.META.get('REMOTE_ADDR', '127.0.0.1'),
        'city': 'Istanbul',
        'country': 'Turkey',
        'zipCode': '34732'
    }

    address = {
        'contactName': f"{user.first_name} {user.last_name}" if user.first_name else user.username,
        'city': 'Istanbul',
        'country': 'Turkey',
        'address': 'Nisantasi',
        'zipCode': '34732'
    }

    # Basket Items
    basket_items = [
        {
            'id': 'BI101',
            'name': 'Postless Pro Subscription',
            'category1': 'SaaS',
            'itemType': 'VIRTUAL',
            'price': '500.00'
        }
    ]

    request_data = {
        'locale': 'tr',
        'conversationId': f'conv_{user.id}',
        'price': '500.00',
        'paidPrice': '500.00',
        'currency': 'TRY',
        'basketId': f'B_{user.id}',
        'paymentGroup': 'PRODUCT',
        'callbackUrl': settings.IYZICO_CALLBACK_URL,
        'enabledInstallments': ['2', '3', '6', '9'],
        'buyer': buyer,
        'shippingAddress': address,
        'billingAddress': address,
        'basketItems': basket_items
    }

    checkout_form_initialize = iyzipay.CheckoutFormInitialize().create(request_data, options)
    # result = checkout_form_initialize.read().decode('utf-8')
    # Use the helper function provided by the library
    return checkout_form_initialize.read().decode('utf-8')

def retrieve_checkout_form_result(token):
    options = get_iyzipay_options()
    request_data = {
        'locale': 'tr',
        'conversationId': 'conv_callback',
        'token': token
    }
    checkout_form = iyzipay.CheckoutForm().retrieve(request_data, options)
    return checkout_form.read().decode('utf-8')
