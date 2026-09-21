"""认证 API：登录（JWT）/登出/当前用户"""
from django.contrib.auth import authenticate
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get('username', '')
    password = request.data.get('password', '')
    user = authenticate(username=username, password=password)
    if not user:
        return Response({'error': '用户名或密码错误'}, status=401)
    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': {'id': user.id, 'username': user.username,
                 'is_superuser': user.is_superuser},
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    u = request.user
    return Response({'id': u.id, 'username': u.username, 'is_superuser': u.is_superuser})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_list(request):
    """用户列表（使用人筛选用，只返回 id/username）"""
    from django.contrib.auth import get_user_model
    U = get_user_model()
    rows = list(U.objects.values('id', 'username')[:200])
    return Response({'count': len(rows), 'results': rows})
