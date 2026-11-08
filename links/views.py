from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import LinkForm, RegistrationForm
from .models import ShortLink
from .services import LinkService, RedirectService


def home(request):
    return redirect("link_list" if request.user.is_authenticated else "login")


def register(request):
    if request.user.is_authenticated:
        return redirect("link_list")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        return redirect("link_list")
    return render(request, "links/register.html", {"form": form})


login_view = LoginView.as_view(template_name="links/login.html")
logout_view = LogoutView.as_view()


@login_required
def link_list(request):
    return render(request, "links/list.html", {"links": LinkService().list_for(request.user)})


@login_required
def link_create(request):
    form = LinkForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        LinkService().create(request.user, form.cleaned_data["original_url"])
        return redirect("link_list")
    return render(request, "links/create.html", {"form": form})


@login_required
@require_POST
def link_delete(request, pk):
    if not LinkService().delete_for(request.user, pk):
        raise Http404("Посилання не знайдено")
    return redirect("link_list")


def follow_link(request, code):
    try:
        url = RedirectService().resolve_and_count(code)
    except ShortLink.DoesNotExist as exc:
        raise Http404("Код не знайдено") from exc
    return HttpResponseRedirect(url)
