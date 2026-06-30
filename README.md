<h1 align="center">BEEG API</h1> 

<div align="center">
    <a href="https://pepy.tech/project/beeg_api"><img src="https://static.pepy.tech/badge/beeg_api" alt="Downloads"></a>
    <a href="https://github.com/EchterAlsFake/beeg_api/workflows/"><img src="https://github.com/EchterAlsFake/beeg_api/workflows/CodeQL/badge.svg" alt="CodeQL Analysis"/></a>
    <a href="https://echteralsfake.me/ci/beeg_api/badge.svg"><img src="https://echteralsfake.me/ci/beeg_api/badge.svg" alt="Sync API Tests"/></a>
    </div>

# Disclaimer
> [!IMPORTANT]
> This is an unofficial and unaffiliated project. Please read the full disclaimer before use:
> **[DISCLAIMER.md](https://github.com/EchterAlsFake/API_Docs/blob/master/Disclaimer.md)**
>
> By using this project you agree to comply with the target site’s rules, copyright/licensing requirements,
> and applicable laws. Do not use it to bypass access controls or scrape at disruptive rates.

# Features
- Fetch videos + metadata
- Download videos
- Asynchronous
- Built-in caching
- Easy interface
- Great type hinting

#### Networking Features
- HTTP 2.0 / HTTP 3.0
- Browser impersonation
- Custom JA3
- All proxy types
- Proxy authentication
- Speed Limit
- DNS over HTTPS
- And even more...
- All of this is configurable and can be adjusted as you like!

# Supported Platforms
This API has been tested and confirmed working on:

- Windows 11 (x64) 
- macOS Sequoia (x86_64)
- Linux (Arch) (x86_64)
- Android 16 (aarch64)

# Quickstart

### Have a look at the [Documentation](https://github.com/EchterAlsFake/API_Docs/blob/master/Porn_APIs/beeg_api.md) for more details
- Install the library with `pip install beeg_api`


```python
import asyncio
from beeg_api import Client, DownloadConfigHLS
# Initialize a Client object

async def do_something():    
    client = Client()
    
    # Fetch a video
    video_object = await client.get_video("<insert_url_here>")
    
    # Information from Video objects
    print(video_object.title)
    print(video_object.likes)
    # Download the video
    
    config = DownloadConfigHLS(
        quality="best", # Half, Worst, 144p, 240p etc...
        path="<output_path>" # And other options... please look at the docs
    )
    
    await video_object.download(config)

asyncio.run(do_something())    
# SEE DOCUMENTATION FOR MORE
```


# Support (Donations)
I am developing all my projects entirely for free. I do that because I have fun and I don't want
to charge 30€ like other people do.

However, if you find my work useful, please consider donating something. A tiny amount such as 1€
means a lot to me.

Paypal: https://paypal.me/EchterAlsFake
<br>XMR (Monero): `42XwGZYbSxpMvhn9eeP4DwMwZV91tQgAm3UQr6Zwb2wzBf5HcuZCHrsVxa4aV2jhP4gLHsWWELxSoNjfnkt4rMfDDwXy9jR`


# Contribution
Do you see any issues or having some feature requests? Simply open an Issue or talk
in the discussions.

Pull requests are also welcome.

# License
Licensed under the LGPLv3 License
<br>Copyright (C) 2023–2026 Johannes Habel
