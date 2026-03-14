# License Recommendation

## Recommendation

Use **Apache-2.0** for the first public release.

## Why Apache-2.0

For this repository, Apache-2.0 is a strong default because it is:

- permissive
- broadly understood
- business-friendly
- explicit about patent grants
- compatible with the “foundation / toolkit” positioning of this repo

That fits `agent-hub` better than a copyleft license at this stage.

## Why Not Delay Forever

If the repo is meant to be public and collaborative, it should have an explicit license before broad publication.

Without a license:

- others cannot safely adopt it
- companies will hesitate to test it
- contribution expectations stay ambiguous

## Alternatives

### MIT

Pros:

- very short
- very common
- easiest to scan

Cons:

- weaker patent framing
- less explicit contributor protection

MIT is also acceptable, but Apache-2.0 is the better fit if you expect serious external use.

### GPL / AGPL

Pros:

- stronger reciprocity

Cons:

- higher adoption friction
- less aligned with “reference local-first control plane” positioning

Not recommended for the first release.

## Practical Recommendation

If you want the safest broad-adoption default:

- choose `Apache-2.0`

If you want the shortest, simplest text and do not care as much about patent language:

- choose `MIT`

## Next Action

Before publishing:

1. decide `Apache-2.0` vs `MIT`
2. add `LICENSE`
3. mention the choice in the first public release notes
