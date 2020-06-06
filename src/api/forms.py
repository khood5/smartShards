from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField
from wtforms.validators import DataRequired, IPAddress, Optional


class PeerForm(FlaskForm):
    ip = StringField('new_ip', validators=[Optional(), DataRequired(), IPAddress()])
    port = IntegerField('new_port', validators=[Optional(), DataRequired()], default=5000)
    committee_id = StringField('Committee ID', validators=[Optional(), DataRequired()])
    add_submit = SubmitField('Add', id='add_submit')
    rm_submit = SubmitField('Remove', id='rm_submit')


class OverlayJoinForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    submit = SubmitField('Join', id='join_submit')


class OverlayCreateForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    old_submit = SubmitField('Create', id='create_submit')
