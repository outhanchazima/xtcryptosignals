__author__ = "Paulo Antunes"
__copyright__ = "Copyright 2018, XTCryptoSignals"
__credits__ = ["Paulo Antunes", ]
__license__ = "GPL"
__maintainer__ = "Paulo Antunes"
__email__ = "pjmlantunes@gmail.com"


import json
import redis
from datetime import timedelta
from celery.task import task
from celery.exceptions import Ignore
from celery import states
from pywebpush import webpush, WebPushException
from xtcryptosignals.tasks import settings as s
from xtcryptosignals.common.utils import use_mongodb
from xtcryptosignals.tasks.utils import convert_to_seconds
from xtcryptosignals.server.api.notification.models import (
    NotificationRule,
    Notification,
)
from xtcryptosignals.tasks.models.history import History


red = redis.Redis.from_url(s.BROKER_URL)


@task(bind=True)
@use_mongodb(
    db=s.MONGODB_NAME,
    host=s.MONGODB_HOST,
    port=s.MONGODB_PORT,
    connect=False
)
def update(self):
    logger = self.get_logger()

    for notif in NotificationRule.objects():
        exchange_and_pair = s.EXCHANGES_AND_PAIRS_OF_REFERENCE[notif.coin_token]

        model_history = type('History{}'.format(notif.interval), (History,), {})
        row_history = model_history.objects(
            symbol=notif.coin_token+exchange_and_pair['pair'],
            source=exchange_and_pair['name']
        ).first()

        if not row_history:
            continue

        obj_history = row_history.to_dict(frequency=notif.interval)

        try:
            obj_history_change = obj_history['{}_change'.format(notif.metric)]
        except KeyError:
            continue

        try:
            price = obj_history['price_usdt']
        except KeyError:
            continue

        logger.warning('{} {} {}'.format(
            obj_history['ticker'], notif.metric, obj_history_change)
        )

        if notif.percentage > 0.0:
            if obj_history_change < notif.percentage:
                continue

            message_templ = '{} {} is up {}% within {}. ' \
                            'Current Price is {:,.4f} USDT.'
            message = message_templ.format(
                obj_history['ticker'],
                notif.metric.capitalize(),
                obj_history_change,
                notif.interval,
                price
            )
        elif obj_history_change > notif.percentage:
            continue

        else:
            message_templ = '{} {} is down {}% within {}. ' \
                            'Current Price is {:,.2f} USDT.'
            message = message_templ.format(
                obj_history['ticker'],
                notif.metric.capitalize(),
                obj_history_change,
                notif.interval,
                price
            )

        if red.get(message):
            continue

        red.setex(
            name=message,
            value=1,
            time=timedelta(
                seconds=convert_to_seconds(notif.interval)
            )
        )

        Notification(message=message, user=notif.user).save()

        try:
            try:
                webpush(
                    subscription_info=notif.user.metadata['subscription'],
                    data=json.dumps(dict(
                        title='XTCryptoSignals',
                        message=message,
                        url='{}/ticker/{symbol}/{frequency}'.format(
                            s.SERVER_ADDRESS, **obj_history
                        ),
                        icon='{}{ticker}.png'.format(
                            s.STATIC_COINS_TOKENS_LOGOS_FOLDER, **obj_history
                        ),
                    )),
                    vapid_private_key=s.VAPID_PRIVATE_KEY,
                    vapid_claims=dict(sub='mailto:{}'.format(s.VAPID_CLAIMS)),
                )
            except WebPushException as error:
                if error.response and error.response.json():
                    extra = error.response.json()
                    logger.error(
                        "Remote service replied with a {}:{}, {}",
                        extra.code,
                        extra.errno,
                        extra.message
                    )
        except Exception as error:
            self.update_state(state=states.FAILURE, meta=str(error))
            raise Ignore()
        finally:
            pass
