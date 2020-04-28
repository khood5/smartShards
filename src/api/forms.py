from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField
from wtforms.validators import DataRequired, IPAddress, Optional


class AddPeerForm(FlaskForm):
    new_ip = StringField('new_ip', validators=[Optional(), DataRequired(), IPAddress()])
    new_port = IntegerField('new_port', validators=[Optional(), DataRequired()], default=5000)
    new_submit = SubmitField('Add', id='add_submit')


class RmPeerForm(FlaskForm):
    old_ip = StringField('old_ip', validators=[Optional(), DataRequired(), IPAddress()])
    old_port = IntegerField('old_port', validators=[Optional(), DataRequired()], default=5000)
    old_submit = SubmitField('Remove', id='rm_submit', )
