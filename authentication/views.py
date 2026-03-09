from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from .forms import LoginForm, CustomPasswordChangeForm, ChangeUsernameForm


@require_http_methods(["GET", "POST"])
def user_login(request):
    """Login view - allow both authenticated and unauthenticated users"""
    
    if request.user.is_authenticated:
        return redirect('main:mainpage')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            nis = form.cleaned_data['nis']
            password = form.cleaned_data['password']
            
            try:
                user = User.objects.get(username=nis)
                user = authenticate(request, username=nis, password=password)
                
                if user is not None:
                    login(request, user)
                    messages.success(request, f'Selamat datang, {user.first_name}!')
                    return redirect('main:mainpage')
                else:
                    messages.error(request, 'Password salah. Silahkan coba lagi.')
            except User.DoesNotExist:
                messages.error(request, 'NIS tidak ditemukan di sistem.')
        else:
            messages.error(request, 'Silahkan isi semua field dengan benar.')
    else:
        form = LoginForm()
    
    return render(request, 'login.html', {'form': form})


@require_http_methods(["GET", "POST"])
@login_required(login_url='authentication:login')
def change_password(request):
    """Change password view"""
    
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Password Anda berhasil diubah!')
            return redirect('main:mainpage')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CustomPasswordChangeForm(request.user)
    
    context = {
        'form': form,
        'page_title': 'Ubah Password'
    }
    return render(request, 'change_password.html', context)


@require_http_methods(["GET", "POST"])
@login_required(login_url='authentication:login')
def change_username(request):
    """Change username view"""
    
    if request.method == 'POST':
        form = ChangeUsernameForm(request.POST)
        if form.is_valid():
            new_username = form.cleaned_data['new_username']
            password = form.cleaned_data['password']
            
            user = authenticate(request, username=request.user.username, password=password)
            
            if user is not None:
                user.username = new_username
                user.save()
                messages.success(request, 'Username Anda berhasil diubah!')
                return redirect('main:mainpage')
            else:
                messages.error(request, 'Password yang Anda masukkan salah.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        form = ChangeUsernameForm()
    
    context = {
        'form': form,
        'page_title': 'Ubah Username'
    }
    return render(request, 'change_username.html', context)


@require_http_methods(["POST"])
@login_required(login_url='authentication:login')
def user_logout(request):
    """Logout view"""
    # Clear all pending messages before logging out
    storage = messages.get_messages(request)
    for _ in storage:
        pass  # Consume the iterator to clear messages
    logout(request)
    messages.success(request, 'Anda telah berhasil keluar.')
    return redirect('authentication:login')
