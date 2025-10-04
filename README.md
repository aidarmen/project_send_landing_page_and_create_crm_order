
## created Virtual Environment

```
python -m venv venv
```


## Activate the Virtual Environment
```
.\venv\Scripts\activate
```

## Creating a requirements.txt file:
```
pip freeze > requirements.txt
```

## Installing packages from a requirements.txt file:
```
pip install -r requirements.txt
```

## PowerShell-native (create a user)
```
$body = @{
  name = "Aruzhan"
  phone = "+7701..."
  email = "a@ex.kz"
  filial_id = 17
  customer_account_id = 700371
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5000/admin/user" `
  -ContentType "application/json" `
  -Body $body
```
## Create an offer (PowerShell)
```
$offerBody = @{
  title  = "Home Internet 200 + TV Basic"
  bundle = "bundle"                  # internet | fms | tv | bundle
  price  = 6990
  currency = "KZT"
  details = @{ speed = "200 Mbps"; tv_channels = "120"; fms_desc = "Family Media Service promo" }

  # mapping to your Order API
  product_offer_id         = 123456
  product_offer_struct_id  = 555
  po_struct_element_id     = 777
  product_num              = "ACC-001"
  resource_spec_id         = 4444
} | ConvertTo-Json -Depth 5

$offer = Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5000/admin/offer" `
  -ContentType "application/json" `
  -Body $offerBody

$offer
# Expect: {"offer_id": <number>}
```

## Create a link for user_id = 2 (PowerShell)
```
$linkBody = @{
  user_id    = 2
  offer_id   = $offer.offer_id
  external_id = "SMS-2025-0001"      # your tracking id
  expires_days = 7                   # optional
} | ConvertTo-Json

$link = Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5000/admin/link" `
  -ContentType "application/json" `
  -Body $linkBody

$link
# Expect: {"link_id":..., "url":"http://localhost:5000/l/<token>", "expires_at":"..."}
```
## Open the customer URL (PowerShell)
```
Start-Process $link.url

```

## run project 
```
.\venv\Scripts\activate
python app.py
```

# For running on dockerfile

1. Установка (PowerShell от имени администратора)

Включите необходимые компоненты Windows (PowerShell):
```
dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
dism /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
```
2. Поставьте WSL 2 и базовый дистрибутив (если ещё не стоит), перезагрузитесь(PowerShell):
```
wsl --install -d Ubuntu
# если уже есть WSL:
wsl --set-default-version 2
```
3. Скачать Docker Desktop

4. Проверка  (PowerShell)
```
docker version
docker compose version
docker info
```

5. Запуск проекта в контейнере, В корне проекта(где Dockerfile и docker-compose.yml):
```
docker compose build
docker compose up -d
docker compose logs -f web
```