__author__ = "Paulo Antunes"
__copyright__ = "Copyright 2018, XTCryptoSignals"
__credits__ = ["Paulo Antunes", ]
__license__ = "GPL"
__maintainer__ = "Paulo Antunes"
__email__ = "pjmlantunes@gmail.com"


from flask import Flask
from flask_login import LoginManager


app = Flask(
    import_name=__name__,
    template_folder='templates',
    # @Note: let nginx or other more resourceful WS serve static content
    static_folder='static',
)

app.jinja_env.auto_reload = app.config['DEBUG']

if app.config['ENV'] == "production":
    app.config.from_object("xtcryptosignals.client.config.ConfigProduction")
    app.config.from_pyfile('settings.prod.py')
else:
    app.config.from_object("xtcryptosignals.client.config.ConfigDevelopment")
    app.config.from_pyfile('settings.dev.py')


login_manager = LoginManager()


def create_app():
    from xtcryptosignals.client.api.auth.views import bp as bp_auth
    from xtcryptosignals.client.api.common.views import bp as bp_common
    from xtcryptosignals.client.api.ticker.views import bp as bp_ticker
    from xtcryptosignals.client.api.contact.views import bp as bp_contact
    from xtcryptosignals.client.api.user.views import bp as bp_user

    bps = (
        bp_auth,
        bp_user,
        bp_ticker,
        bp_contact,
        bp_common,
    )

    for x in bps:
        app.register_blueprint(x)

    login_manager.init_app(app)

    login_manager.login_view = "ticker.index"
    login_manager.session_protection = "strong"

    return app
