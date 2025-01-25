from django.shortcuts import render

def weather_map_view(request):
    return render(request, 'weather_map.html')
