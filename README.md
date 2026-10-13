# Stack IPA

Combines a Spotify IPA you supply with the EeveeSpotify and Chroma tweak packages you supply. Runs entirely in the browser (Python through Pyodide) or from the command line. No Spotify, Eevee or Chroma files are included here.

## Web page

Settings, Pages, Source: Deploy from a branch, pick this branch and the `/docs` folder. Open the published page, choose your Spotify IPA, tap Check files, then Build IPA, then Download IPA. The page downloads EeveeSpotify and Chroma itself through a public CORS relay and refuses any file whose SHA-256 differs from the pinned official release in `docs/pins.json`. If every relay fails, pick your own .deb files under Options. Sign the result with your usual sideloading tool.

Browsers cannot read GitHub release downloads directly, which is why a relay is used. To move to newer releases, update the URLs and hashes in `docs/pins.json`.

## Command line

    cd docs
    python3 -m stackipa --ipa Spotify.ipa --eevee eevee.deb --chroma chroma.deb -o stacked.ipa

Either tweak can be given alone for a staged test. `--dry-run` checks everything without writing the IPA.

## Tests

    python3 -m unittest discover -s tests

## Notes

- The IPA must be decrypted and the main executable thin arm64.
- Chroma builds name the Spotify versions they were made for; a mismatch stops the build unless forced.
- The sideload keychain and App Group fix that Eevee's own workflow adds is not included, and neither is Chroma's Live Activity extension.
- Orion and CydiaSubstrate frameworks are downloaded from the pinned pyzule-rw commit and checked against SHA-256 hashes.
