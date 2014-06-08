import json
from django.contrib.sessions.models import Session
from django.http import HttpResponse
from session_management.models import Visitor
from django.contrib import auth

def dialog_action(request):
    if request.POST.get('action')=='continue':
        session_key=request.session.session_key
        Session.objects.filter(session_key=request.user.visitor.session_key).delete()
        Visitor.objects.create(session_key=session_key, user=request.user)
        result={
                "success": 1,     # 0 - fail, 1 - success, 2 - exception
                "message": "Success/Fail message.",
                "data": {
                    "meta": {},
                    "objects": {
                         'url':'/home/'
                                }
                        }
                }
        return HttpResponse(json.dumps(result), mimetype='application/json')

    elif request.POST.get('action') == 'logout':
        #since we are having auto-logoff functionality with us as well
        #we need to check for session parameter _session_security
        #_session_security is used by session security to judge the
        #auto logoff of the user
        if '_session_security' in request.session:
            del request.session["_session_security"]

        auth.logout(request)
        result={
                "success": 1,     # 0 - fail, 1 - success, 2 - exception
                "message": "Success/Fail message.",
                "data": {
                    "meta": {},
                    "objects": {
                         'url':'/login/'
                                }
                        }
                }
        return HttpResponse(json.dumps(result), mimetype='application/json')