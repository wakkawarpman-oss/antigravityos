from typing import List

import aiohttp


async def check_links(links: List[str]) -> List[str]:
    valid_links: List[str] = []
    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for url in links:
            try:
                async with session.get(url, allow_redirects=True) as res:
                    if 200 <= res.status < 400:
                        valid_links.append(url)
            except aiohttp.ClientError:
                continue

    return valid_links
